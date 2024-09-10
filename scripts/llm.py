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


# =====================
#  Configuration Setup
# =====================

# Load OpenAI models and prompts from the config file
small_model = config.llm_config['small_model']
large_model = config.llm_config['large_model']
system_message = config.llm_config['system_prompt']
hashtags = config.llm_config['hashtags']
category = config.llm_config['category']
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
        logging.warning(f"RateLimitError: {e}. Retrying...")
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


def extract_links(df, link_column='Link', time_column='Time'):
    """
    Extracts links and timestamps from a pandas DataFrame.

    Args:
        df (pd.DataFrame): The DataFrame containing the data.
        link_column (str): The name of the column containing links.
        time_column (str): The name of the column containing timestamps.

    Returns:
        list: A list of dictionaries, each containing the specified link and time columns.
    """
    try:
        # Check if DataFrame is empty
        if df.empty:
            logging.warning("The DataFrame is empty.")
            return []

        # Ensure required columns exist
        if link_column not in df.columns or time_column not in df.columns:
            logging.warning(f"Missing required columns: {link_column} or {time_column}")
            return []

        # Drop rows where 'Link' is null and extract necessary columns
        links = df.dropna(subset=[link_column])[['Link', 'Time']]
        
        # Convert to list of dictionaries
        link_records = links.to_dict('records')
        
        logging.info(f"Extracted {len(link_records)} link records.")
        return link_records

    except Exception as e:
        logging.error(f"Error extracting links: {str(e)}")
        return []


def extract_image_links(df, image_column='Image'):
    """
    Extracts image links from a pandas DataFrame.

    Args:
        df (pd.DataFrame): The DataFrame containing the CSV data.
        image_column (str): The name of the column containing image links.

    Returns:
        list: A list of image links.
    """
    try:
        # Check if DataFrame is empty
        if df.empty:
            logging.warning("The DataFrame is empty.")
            return []

        # Ensure 'Image' column exists
        if image_column not in df.columns:
            logging.warning(f"'{image_column}' column not found in the DataFrame.")
            return []

        # Extract the 'Image' column and convert to list
        image_links = df[image_column].dropna().tolist()  # Drop any NaN values

        logging.info(f"Extracted {len(image_links)} image links.")
        return image_links

    except Exception as e:
        logging.error(f"Error extracting image links: {str(e)}")
        return []


# =====================
#  Link Processing
# =====================

@retry(wait=wait_random_exponential(min=2, max=10), stop=stop_after_attempt(6))
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
        image_links (list): A list of image links.

    Returns:
        dict: A log entry containing the generated post content and associated metadata, or an error entry if an error occurred.
    """
    try:
        # Step 1: Validate the Link
        link = link_info.get('Link')
        if link is None:  # Check if the link is None
            error_message = f"Invalid link found in link_info: {link_info}"
            logging.warning(error_message)
            return {"status": "error", "message": error_message, "link_info": link_info}

        url = f"http://r.jina.ai/{link}"
        logging.info(f"Starting to process link: {url}")

        # Step 2: Fetch Content from the Link
        webpage_content = fetch_url_content(url)

    except requests.exceptions.RequestException as e:
        error_message = f"Error fetching {url}: {e}"
        logging.error(error_message)
        return {"status": "error", "message": error_message, "url": url}

    try:
        # Step 3: Generate Post
        logging.info(f"Successfully fetched webpage content from {url}, now generating post.")
        generated_post = generate_post(webpage_content, link_info.get('Link'), link_info.get('Time'), combined_links, image_links)
        logging.info(f"Post generated successfully for link: {url}")

        # Return the generated post data with a success status
        return {"status": "success", "generated_post": generated_post, "link": link, "og_time": link_info.get('Time')}

    except Exception as e:
        error_message = f"Error generating post for {url}: {e}"
        logging.error(error_message)
        return {"status": "error", "message": error_message, "url": url}

# =====================
#  Pydantic Model for Response
# =====================

# Create an Enum for Hashtags
HashtagEnum = Enum('HashtagEnum', {tag: tag for tag in hashtags})

# Create an Enum for Categories
CategoryEnum = Enum('CategoryEnum', {cat: cat for cat in category})

class PostResponse(BaseModel):
    """
    Pydantic model for the structure of the post response generated by OpenAI.
    """
    post_content: str = Field(..., description="The final generated post content in plain text without any hashtags.")
    hashtags: List[HashtagEnum] = Field(..., description="A list of relevant hashtags for the post.")  # restrict hashtags to the dynamically created Enum
    category: CategoryEnum = Field(..., description="The category for the post, restricted to four predefined categories.")  # restrict category to one of the four categories

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
    logging.info(f"Image query: {image_query}")

    # Fetch a unique image from Pexels API based on the query
    image_link = get_unique_image(api_key=pexels_api_key, image_query=image_query, image_links=image_links)

    if not image_link:
        logging.error(f"No unique image found for link {link}.")
        print(f"No unique image found for link {link}.")
        return None

    # Combine category and hashtags
    combined_hashtags = [data.category.value] + [hashtag.value for hashtag in data.hashtags]

    # Append the processed information to combined_links
    combined_links.append({"Image": image_link})
    logging.info(f"Unique image link: {image_link}")

    # Return the log entry, including the combined hashtags
    return [original_timestamp, llm_timestamp, data.post_content, combined_hashtags, image_link, link, system_message, content, large_model]

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
            {"role": "system", "content": """Your task is to analyze a given social media post related to medicine or healthcare and determine its core message, key content elements, and tone. Based on this analysis, generate a precise and highly relevant search term to query a stock image library (such as Pexels). The search term must adhere to the following guidelines:

	1.	Medical Specificity: Ensure the search term accurately reflects the core medical content of the post. Focus on specific treatments, diseases, medical conditions, or healthcare themes, but avoid overly technical terms or drug names that might not be represented visually (e.g., “atezolizumab” or “bevazicumab”). Instead, translate these concepts into broader, more visually understandable terms (e.g., “immunotherapy for cancer” or “cancer treatment team”).
	2.	Clinical Context and Relevance: Consider the clinical or healthcare setting described in the post. For example, if the post discusses treatment advancements, choose terms that evoke the appropriate environment, like “oncology consultation” or “medical research.” Ensure the search term aligns with the clinical tone of the post (e.g., serious, educational, inspiring).
	3.	Avoiding Ambiguity: When faced with complex or abstract medical topics, distill the key message into clear, visually recognizable terms. For instance, instead of “multiple sclerosis,” consider “nervous system health” or “autoimmune disease diagnosis” depending on the post’s context.
	4.	Handling Drug Trials and Studies: If the post focuses on clinical trials, treatment outcomes, or research findings, generate search terms that reflect these themes without being too abstract. For instance, “cancer treatment trial results” or “doctor analyzing study data.”
	5.	Edge Cases in Medical Content: If the post is highly technical or doesn’t lend itself to obvious visual imagery, create a search term that captures a broader but still relevant healthcare-related concept. For example, if the post discusses molecular mimicry in autoimmune diseases, a suitable term might be “immune system illustration” or “doctor studying immune response.”
	6.	Tone Sensitivity: Ensure the search term reflects the tone of the post, whether it’s informational, professional, or thought-provoking. Avoid search terms that are too casual or not aligned with the post’s seriousness.

Output only the search term in your response, and make it concise yet comprehensive enough to guide the search effectively."""},
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

def log_to_csv_pandas(log_entry, document_id, file_name="databases/llm.csv"):
    """
    Log the generated post content, metadata, and document ID to a CSV file.

    Args:
        log_entry (list): The log entry data to be saved.
        document_id (str): The document ID from Firebase.
        file_name (str): The path to the CSV file.
    """
    try:
        # Append the document ID to the log entry
        log_entry_with_id = log_entry['generated_post'] + [document_id]

        # Define columns, adding 'DocumentID' as the new column
        columns = ["Time", "LLM Timestamp", "Post", "Hashtags", "Image", "Link", "Prompt", "Input", "Model", "DocumentID"]

        # Create a DataFrame for the new log entry
        df_new = pd.DataFrame([log_entry_with_id], columns=columns)

        # Save the log entry to the CSV file
        if not os.path.exists(file_name):
            df_new.to_csv(file_name, index=False)
        else:
            df_new.to_csv(file_name, mode='a', index=False, header=False)

        logging.info(f"Logged data to {file_name} with DocumentID: {document_id}.")
        print(f"Logged {log_entry['generated_post'][5]} to {file_name} with DocumentID: {document_id}.")
    except Exception as e:
        logging.error(f"Error logging data to CSV: {e}")
        print(f"Error logging data to CSV: {e}")


def send_to_firebase(log_entry, url="https://expert-doodle-5gggqrq5g764c9rg-8080.app.github.dev/post"):
    """
    Sends the log entry to the Firebase-connected Flask app and retrieves the documentID.

    Args:
        log_entry (dict): The log entry data to be sent to Firebase.

    Returns:
        str: The document ID from Firebase or an error message.
    """
    try:
        # Ensure log_entry has the 'generated_post' key and is not None
        if not log_entry.get('generated_post'):
            logging.error("No 'generated_post' found in log entry or 'generated_post' is None.")
            return None

        # Extract necessary data from the log_entry['generated_post']
        post_data = {
            'imageURL': log_entry['generated_post'][4],  # Image URL
            'hashtags': log_entry['generated_post'][3],  # Hashtags (includes category + hashtags)
            'source': log_entry['generated_post'][5],    # Source (link)
            'post': log_entry['generated_post'][2]       # Post content
        }

        # Set up the headers including the API key
        headers = {
            'Content-Type': 'application/json',
            'x-api-key': 'fazzu'  # API key for authentication
        }

        # Make a POST request to the Flask app
        response = requests.post(url, json=post_data, headers=headers)

        # Check if the response is successful
        if response.status_code == 201:
            result = response.json()
            logging.info(f"Successfully sent data to Firebase: {result}")
            return result.get('documentID', None)  # Return the documentID from the response
        else:
            logging.error(f"Failed to send data to Firebase. Status code: {response.status_code}, Response: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Error sending data to Firebase: {e}")
        return None


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
    logging.info(f"Unique links to process: {len(combined_links)}")
    print(f"Unique links to process: {len(combined_links)}")

    if not combined_links:
        logging.info("No unique links to process.")
        print("No unique links to process.")
        return

    # Process each link and log the results
    for link_info in combined_links:
        log_entry = process_link(link_info, combined_links, image_links)
        
        # Check if log_entry is valid before proceeding
        if log_entry and log_entry.get('status') == 'success':
            # Send the log entry to Firebase and get the documentID
            document_id = send_to_firebase(log_entry)

            # Log the entry to CSV along with the documentID
            log_to_csv_pandas(log_entry, document_id)
        else:
            logging.warning(f"Skipping entry due to missing or invalid log entry for link: {link_info.get('Link')}")


# Entry point for the script
if __name__ == "__main__":
    main()