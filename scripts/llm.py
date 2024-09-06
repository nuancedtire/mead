import os
import logging
import requests
import pandas as pd
from datetime import datetime
import config
import openai
from openai import OpenAI, RateLimitError
from tenacity import retry, stop_after_attempt, wait_random_exponential
from pydantic import BaseModel, Field, ValidationError
from typing import List
import time
from enum import Enum


# =====================
#  Logging Setup
# =====================

def setup_logger(log_file_path="logs/llm.log"):
    """
    Set up logging for the application, creating the necessary directories and log files.
    
    Args:
        log_file_path (str): The path to the log file. Defaults to "logs/llm.log".
    """
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
    logging.basicConfig(
        filename=log_file_path,
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logging.info("Logging setup complete.")
    print("Logging setup complete.")


# =====================
#  Configuration Setup
# =====================

# Load OpenAI models and prompts from the config file
small_model = config.llm_config['small_model']
large_model = config.llm_config['large_model']
system_message = config.llm_config['system_prompt']
hashtags = config.llm_config['hashtags']
pexels_api_key = "fp8Urerp0HYAsM2UmutJhXbhuSOeXEu75TJvzmIEYOVQ51ckelerwvPk"


# =====================
#  OpenAI API Setup
# ===================== 
openai.api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI()


# =====================
#  Retry Logic for OpenAI API
# =====================

@retry(wait=wait_random_exponential(min=40, max=120), stop=stop_after_attempt(6))
def completion_with_backoff(**kwargs):
    """
    Perform a completion request to the OpenAI API with retry logic. In case of rate limit 
    errors, it will back off and retry the request.

    Args:
        kwargs: The arguments to be passed to the OpenAI API call.

    Returns:
        dict: The response from the OpenAI API.
    """
    try:
        if 'response_format' in kwargs:
            return client.beta.chat.completions.parse(**kwargs)
        else:
            return client.chat.completions.create(**kwargs)
    except RateLimitError as e:
        # Handle rate limit errors with exponential backoff
        print(f"RateLimitError: {e}. Retrying...")
        raise


# =====================
#  CSV File Handling
# =====================

def read_csv(file_path):
    """
    Reads a CSV file into a pandas DataFrame.

    Args:
        file_path (str): The path to the CSV file.

    Returns:
        pd.DataFrame: The DataFrame with the contents of the CSV file, or an empty DataFrame if the file doesn't exist.
    """
    if not os.path.exists(file_path):
        logging.warning(f"{file_path} does not exist, skipping...")
        print(f"{file_path} does not exist, skipping...")
        return pd.DataFrame()  # Return empty dataframe to avoid errors later
    return pd.read_csv(file_path)


def extract_links(df):
    """
    Extracts links and timestamps from a pandas DataFrame.

    Args:
        df (pd.DataFrame): The DataFrame containing the CSV data.

    Returns:
        list: A list of dictionaries, each containing 'Link', 'Time', and optionally 'Image'.
    """
    required_columns = ['Link']
    if not all(col in df.columns for col in required_columns):
        logging.warning("Missing required columns in the CSV.")
        print("Missing required columns in the CSV.")
        return []

    links = df.dropna(subset=['Link'])  # Drop rows where 'Link' is null
    if 'Image' in df.columns:
        return links[['Link', 'Time', 'Image']].to_dict('records')
    return links[['Link', 'Time']].to_dict('records')


def extract_image_links(df):
    """
    Extracts image links from a pandas DataFrame.

    Args:
        df (pd.DataFrame): The DataFrame containing the CSV data.

    Returns:
        list: A list of image links.
    """
    if 'Image' not in df.columns:
        logging.warning("Image column not found in the CSV file.")
        return []  # Return an empty list if 'Image' column is not found

    return df['Image'].tolist()


# =====================
#  Link Processing
# =====================

@retry(wait=wait_random_exponential(min=2, max=10), stop=stop_after_attempt(3))
def fetch_url_content(url):
    """
    Fetch the content of a URL with retry logic.

    Args:
        url (str): The URL to fetch.

    Returns:
        str: The content of the fetched URL.
    """
    response = requests.get(url)
    response.raise_for_status()
    return response.text


def process_link(link_info, combined_links, image_links):
    """
    Processes a single link by fetching its content and generating a post using OpenAI.

    Args:
        link_info (dict): A dictionary containing 'Link', 'Time', and optionally 'Image URL'.
        combined_links (list): A list of previously processed links for comparison.

    Returns:
        list: A log entry containing the generated post content and associated metadata, or None if an error occurred.
    """
    try:
        link = link_info.get('Link')
        if link is None:  # Check if the link is None
            logging.warning(f"Invalid link found in link_info: {link_info}")
            return None
        url = f"http://r.jina.ai/{link}"
        content = fetch_url_content(url)
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching {url}: {e}")
        print(f"Error fetching {url}: {e}")
        return None

    return generate_post(content, link_info.get('Link'), link_info.get('Time'), combined_links, image_links)


# =====================
#  Pydantic Model for Response
# =====================

HashtagEnum = Enum('HashtagEnum', {tag: tag for tag in hashtags})
class PostResponse(BaseModel):
    """
    Pydantic model for the structure of the post response generated by OpenAI.
    """
    post_content: str = Field(..., description="The final generated post content without any hashtags")
    hashtags: List[HashtagEnum] = Field(..., description="A list of relevant hashtags for the post.")  # restrict hashtags to the dynamically created Enum


# =====================
#  OpenAI API and Post Generation
# =====================

def call_openai(**kwargs):
    """
    Call the OpenAI API with retry logic.

    Args:
        model (str): The model to use for the OpenAI API call.
        messages (list): The list of messages to send to the OpenAI API.

    Returns:
        dict: The response from the OpenAI API.
    """
    return completion_with_backoff(**kwargs)


def generate_post(webpage_content, link, original_timestamp, combined_links, image_links):
    """
    Generates post content from webpage content using the OpenAI API.

    Args:
        webpage_content (str): The content of the webpage.
        link (str): The link to the webpage.
        original_timestamp (str): The original timestamp when the link was recorded.
        combined_links (list): A list of previously processed links.
        image_links (list): A list of previously used image links.

    Returns:
        list: A log entry with the generated post content, hashtags, image URL, and metadata.
    """
    
    # First call to OpenAI for checking if the content is an article
    formatted_content = call_openai(
        model=small_model,
        messages=[
            {"role": "system", "content": "Determine if the provided webpage contains a full article. If it does not contain an article, reply with only 'None'. If the webpage contains an article, convert the entire content into plain text, preserving the original text without summarization, additions, or omissions."},
            {"role": "user", "content": webpage_content}
        ],
        temperature=0.2
    )

    # If no valid article was found, exit early
    if formatted_content.choices[0].message.content.strip().lower() == 'none':
        logging.info(f"No article found for link {link}.")
        print(f"No article found for link {link}.")
        return None

    content = formatted_content.choices[0].message.content.strip()
    if not content:
        logging.info(f"Empty content for link {link}.")
        print(f"Empty content for link {link}.")
        return None

    # Use PostResponse directly in response_format
    post_response = call_openai(
        model=large_model,
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": f"Source: {link} \n{content}"}
        ],
        response_format=PostResponse  # Specify PostResponse directly
    )

    # Parse response is handled automatically because we specified PostResponse in response_format
    try:
        data = post_response.choices[0].message.parsed  # .parsed gives the validated Pydantic object
    except ValidationError as e:
        logging.error(f"Validation error for link {link}: {e}")
        print(f"Validation error for link {link}: {e}")
        return None

    # Generate a timestamp for when the post is processed
    llm_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Generate a query to search for images related to the post content
    image_query = get_image_query(data.post_content, small_model)

    # Fetch a unique image from Pexels API based on the query
    image_link = get_unique_image(api_key=pexels_api_key, image_query=image_query, image_links=image_links)

    if not image_link:
        logging.error(f"No unique image found for link {link}.")
        print(f"No unique image found for link {link}.")
        return None

    combined_links.append({"Image": image_link})
    return [original_timestamp, llm_timestamp, data.post_content, [hashtag.value for hashtag in data.hashtags], image_link, link, system_message, content, large_model]

def get_image_query(post_content, model):
    """
    Generate a search query for images based on the post content using OpenAI.

    Args:
        post_content (str): The content of the post.
        model (str): The model to use for the OpenAI API.

    Returns:
        str: The generated search query.
    """
    query_response = call_openai(
        model=model,
        messages=[
            {"role": "system", "content": "Analyze the social media post provided to determine its main topic and key content elements. Based on this analysis, generate a precise and relevant search term suitable for querying a stock image library. The search term should be specific enough to accurately reflect the post’s content while avoiding overly broad terms like ‘machine learning’ or ‘healthcare.’ This keyword will be used to find a fitting thumbnail image from the Pexels stock image library that matches the post’s message and tone. Respond only with the search term."},
            {"role": "user", "content": post_content}
        ],
        max_tokens=1024
    )
    return query_response.choices[0].message.content.strip()


def get_unique_image(api_key, image_query, image_links):
    """
    Fetches a unique image URL from the Pexels API based on the search query.

    Args:
        api_key (str): The API key for Pexels.
        image_query (str): The search query to find an image.
        image_links (list): A list of previously used image links.

    Returns:
        str: The URL of the unique image, or None if no unique image was found.
    """
    headers = {"Authorization": api_key}
    url = "https://api.pexels.com/v1/search"
    params = {"query": image_query, "per_page": 10, "page": 1}

    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()

        if data.get('photos'):
            for photo in data['photos']:
                potential_image_link = photo['src']['original']

                # Check against image_links
                if not any(normalize_url(link) == normalize_url(potential_image_link) for link in image_links):
                    return potential_image_link

            logging.CRITICAL(f"No unique image found for query '{image_query}'.")
            print(f"No unique image found for query '{image_query}'.")
            return None
        else:
            logging.CRITICAL(f"No photos returned from Pexels for query '{image_query}'.")
            print(f"No photos returned from Pexels for query '{image_query}'.")
            return None
    else:
        logging.ERROR(f"Image request failed with status code {response.status_code} for query '{image_query}'.")
        print(f"Image request failed with status code {response.status_code} for query '{image_query}'.")
        return None


def normalize_url(url):
    """
    Normalize a URL by removing trailing slashes and converting to lowercase.

    Args:
        url (str): The URL to normalize.

    Returns:
        str: The normalized URL.
    """
    if not url:
        return None
    return url.strip().rstrip('/').lower()


# =====================
#  Logging to CSV
# =====================

def log_to_csv_pandas(log_entry, file_name="databases/llm.csv"):
    """
    Log the generated post content and metadata to a CSV file.

    Args:
        log_entry (list): The log entry data to be saved.
        file_name (str): The path to the CSV file.
    """
    try:
        df_new = pd.DataFrame([log_entry], columns=["Time", "LLM Timestamp", "Post", "Hashtags", "Image", "Link", "Prompt", "Input", "Model"])

        if not os.path.exists(file_name):
            df_new.to_csv(file_name, index=False)
        else:
            df_new.to_csv(file_name, mode='a', index=False, header=False)

        logging.info(f"Logged data to {file_name}.")
        print(f"Logged data to {file_name}.")
    except Exception as e:
        logging.error(f"Error logging data to CSV: {e}")
        print(f"Error logging data to CSV: {e}")


# =====================
#  Main Logic
# =====================

def get_unique_links(csv_files, llm_links):
    """
    Get unique links from multiple CSV files by filtering out already processed links.

    Args:
        csv_files (list): List of CSV file paths to extract links from.
        llm_links (list): List of previously processed links.

    Returns:
        list: List of unique links to process.
    """
    combined_links = []
    for file in csv_files:
        df = read_csv(file)
        links = extract_links(df)
        combined_links += links

    return {normalize_url(link['Link']): link for link in combined_links if normalize_url(link['Link']) not in llm_links}.values()

def main():
    """
    Main function that handles link extraction, processing, and logging of posts generated by OpenAI.
    """
    # Setup logging
    setup_logger()

    # List of CSV files to process
    csv_files = ['databases/meds.csv', 'databases/sifted.csv', 'databases/scape.csv']

    # Extract links that have already been processed
    llm_file_path = 'databases/llm.csv'
    if os.path.exists(llm_file_path):
        llm_links = [normalize_url(entry['Link']) for entry in extract_links(read_csv(llm_file_path))]
        image_links = extract_image_links(read_csv(llm_file_path))
    else:
        llm_links = []
        image_links = []  # Initialize empty image links list if file doesn't exist

    # Get unique links from the CSV files that haven't been processed yet
    combined_links = list(get_unique_links(csv_files, llm_links))

    if not combined_links:
        logging.info("No unique links to process.")
        print("No unique links to process.")
        return

    # Process each link and log the results
    for link_info in combined_links:
        log_entry = process_link(link_info, combined_links, image_links)
        if log_entry:
            log_to_csv_pandas(log_entry)


# Entry point for the script
if __name__ == "__main__":
    main()