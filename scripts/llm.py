import os
import csv
import logging
import requests
import pandas as pd
from datetime import datetime
import config
import openai
from openai import OpenAI
import json
from tenacity import retry, stop_after_attempt, wait_random_exponential
from pydantic import BaseModel, Field
from typing import List
from openai import RateLimitError
from pydantic import ValidationError
import time

# Set up logging
log_file_path = "logs/llm.log"
os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
logging.basicConfig(filename=log_file_path, level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Load configuration
small_model = config.llm_config['small_model']
large_model = config.llm_config['large_model']
system_message = config.llm_config['system_prompt']
hashtags = config.llm_config['hashtags']

# Retrieve the API key from the environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

client = OpenAI()

@retry(wait=wait_random_exponential(min=40, max=120), stop=stop_after_attempt(6))
def completion_with_backoff(**kwargs):
    try:
        return client.chat.completions.create(**kwargs)
    except RateLimitError as e:
        wait_time = 180  # 3 minutes
        if 'Requested 1' in str(e) and 'Try again in' in str(e):
            # Extract wait time from error message if available
            try:
                wait_time = int(str(e).split('Try again in')[1].split('s')[0].strip()) + 60
            except:
                pass

        logging.warning(f"Rate limit exceeded. Waiting for {wait_time} seconds before retry: {e}")
        time.sleep(wait_time)
        raise

def extract_links_from_csv_pandas(file_path):
    """
    Extracts links and associated timestamps from a CSV file.
    
    Args:
        file_path (str): Path to the CSV file.
        
    Returns:
        list: A list of dictionaries, each containing 'Link', 'Time', 
              and optionally 'Image URL'.
    """
    try:
        if not os.path.exists(file_path):
            logging.warning(f"{file_path} does not exist, skipping...")
            print(f"{file_path} does not exist, skipping...")
            return []
        df = pd.read_csv(file_path)
        
        # Check if required columns exist
        if 'Link' not in df.columns or 'Time' not in df.columns:
            logging.warning(f"{file_path} does not contain 'Link' or 'Time' column.")
            print(f"{file_path} does not contain 'Link' or 'Time' column.")
            return []

        # Extract relevant columns
        if 'Image URL' in df.columns:
            links_with_images = df[['Link', 'Time', 'Image URL']].dropna(subset=['Link']).to_dict('records')
        else:
            links_with_images = df[['Link', 'Time']].dropna().to_dict('records')

        logging.info(f"Loaded {len(links_with_images)} links from {file_path}.")
        print(f"Loaded {len(links_with_images)} links from {file_path}.")
        return links_with_images
    except Exception as e:
        logging.error(f"Error reading {file_path}: {e}")
        print(f"Error reading {file_path}: {e}")
        return []

def process_link(link_info, combined_links):
    """
    Processes a link by fetching its content and generating a post using OpenAI.
    
    Args:
        link_info (dict): A dictionary containing 'Link', 'Time', 
                          and optionally 'Image URL'.
                          
    Returns:
        list: A log entry containing timestamps, generated post content, 
              image URL, and other metadata, or None if an error occurred.
    """
    try:
        link = link_info.get('Link')
        original_timestamp = link_info.get('Time')
        image_url = link_info.get('Image URL')
        
        url = f'http://r.jina.ai/{link}'
        response = requests.get(url)
        response.raise_for_status()
        webpage_content = response.text

        # if image_url:
        #     webpage_content = f'Thumbnail image URL: {image_url}  \n{webpage_content}'

        logging.info(f"Successfully fetched data from {url}.")
        print(f"Successfully fetched data from {url}.")
    except requests.exceptions.HTTPError as errh:
        logging.error(f"HTTP Error: {errh}")
        return None
    except requests.exceptions.ConnectionError as errc:
        logging.error(f"Error Connecting: {errc}")
        return None
    except requests.exceptions.Timeout as errt:
        logging.error(f"Timeout Error: {errt}")
        return None
    except requests.exceptions.RequestException as err:
        logging.error(f"Unexpected Error: {err}")
        return None

    return generate_post(webpage_content, link, original_timestamp, combined_links)


# Define the data structure using Pydantic
class PostResponse(BaseModel):
    post_content: str = Field(..., description="The final generated post content based on the article in plain text and emoji. Do not use Markdown formatting")
    hashtags: List[str] = Field(..., description="A list of relevant hashtags for the post.")

def get_unique_image(api_key, image_query, combined_links):
    """
    Fetch up to 10 images from Pexels API based on the query and return the first unique image
    that has not been used before (not present in combined_links).

    Args:
        api_key (str): Pexels API key.
        image_query (str): Search term for the Pexels API.
        combined_links (list): List of previously used image links to check for duplicates.

    Returns:
        str: The URL of the first unique image, or None if no unique image is found.
    """

    headers = {
        "Authorization": api_key
    }
    url = "https://api.pexels.com/v1/search"
    params = {
        "query": image_query,
        "per_page": 10,
        "page": 1
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        data = response.json()

        if data.get('photos'):
            for photo in data['photos']:
                potential_image_link = photo['src']['original']

                # Normalize the potential image link and check against combined_links
                if not any(normalize_url(link_info.get('Image')) == normalize_url(potential_image_link) 
                           for link_info in combined_links if link_info.get('Image')):
                    return potential_image_link

            print(f"No unique image found for query '{image_query}'.")
            return None
        else:
            print(f"No photos returned from Pexels for query '{image_query}'.")
            return None
    else:
        print(f"Image request failed with status code {response.status_code} for query '{image_query}'.")
        return None

def generate_post(webpage_content, link, original_timestamp, combined_links):
    """
    Generates post content using the OpenAI API and formats it with the 
    original and current timestamps.
    
    Args:
        webpage_content (str): The content of the webpage to generate a post from.
        link (str): The link associated with the webpage.
        original_timestamp (str): The timestamp when the link was first recorded.
        
    Returns:
        list: A log entry including the original and LLM timestamps, 
              generated post content, and hashtags, or None if an error occurred.
    """
    check = completion_with_backoff(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Determine if the provided webpage contains a full article. If it does not contain an article, reply None. If the webpage contains an article, convert the entire content into plain text, preserving the original text without summarization, additions, or omissions."},
            {"role": "user", "content": webpage_content}
        ]
    )
    
    # If the check returns 'None', exit the function
    if check.choices[0].message.content.strip().lower() == 'none':
        logging.info(f"No valid article found for link {link}.")
        print(f"No valid article found for link {link}.")
        return None
    
    # Use the validated article content for further processing
    formatted_content = check.choices[0].message.content

    # Check if formatted_content is None or empty, and return early if it is
    if not formatted_content.strip():
        logging.info(f"Formatted content is empty for link {link}. Exiting function.")
        return None

    response = completion_with_backoff(
        model=large_model,
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": f"Source: {link}  \n{formatted_content}"}
            ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "post_with_hashtags",
                "schema": {
                    "type": "object",
                    "properties": {
                        "post_content": {
                            "type": "string",
                            "description": "The final generated post content based on the article in plain text and emoji. Do not use Markdown formatting"
                            },
                        "hashtags": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": hashtags
                            },
                            "description": "A list of relevant hashtags for the post."
                        }
                    },
                    "required": [
                        "post_content",
                        "hashtags"
                    ]
                }
            }
        }
    )
    
    full_response = response.choices[0].message.content

    try:
        data = PostResponse.parse_raw(full_response)
    except ValidationError as e:
        logging.error(f"Validation error when parsing response: {e}")
        print(f"Validation error: {e}")
        
        # Return None or handle as needed
        return None

    llm_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    keywords = completion_with_backoff(
        model=small_model,
        messages=[
            {"role": "system", "content": "Analyze the social media post provided to determine its main topic and key content elements. Based on this analysis, generate a precise and relevant search term suitable for querying a stock image library. The search term should be specific enough to accurately reflect the post’s content while avoiding overly broad terms like ‘machine learning’ or ‘healthcare.’ This keyword will be used to find a fitting thumbnail image from the Pexels stock image library that matches the post’s message and tone. Respond only with the search term."},
            {"role": "user", "content": data.post_content}
        ]
    )
    
    # Get the generated keyword for the image query
    image_query = keywords.choices[0].message.content

    # Set your Pexels API key
    api_key = "fp8Urerp0HYAsM2UmutJhXbhuSOeXEu75TJvzmIEYOVQ51ckelerwvPk"

    # Fetch the unique image from Pexels API
    image_link = get_unique_image(api_key, image_query, combined_links)

    if image_link is None:
        logging.error(f"No unique image found for link {link}.")
        return None

    # Append the new image to combined_links to ensure no future duplicates
    combined_links.append({"Image": image_link})

    log_entry = [original_timestamp, llm_timestamp, data.post_content, data.hashtags, image_link, link, system_message, formatted_content, large_model]
    logging.info(f"Generated post for link {link}.")
    print(f"Generated post for link {link}.")
    return log_entry
    
def log_to_csv_pandas(log_entry, file_name="databases/llm.csv"):
    """
    Logs the generated post information to a CSV file.

    Args:
        log_entry (list): A list containing the log details.
        file_name (str): The name of the CSV file to log the entry to.
    """
    try:
        df_new = pd.DataFrame([log_entry], columns=["Time", "LLM Timestamp", "Post", "Hashtags", "Image", "Link", "Prompt", "Input", "Model"])

        if not os.path.exists(file_name):
            # If the file doesn't exist, write with header
            df_new.to_csv(file_name, index=False)
        else:
            # If the file exists, append without writing the header again
            df_new.to_csv(file_name, mode='a', index=False, header=False)

        logging.info(f"Logged data to {file_name}.")
        print(f"Logged data to {file_name}.")
    except Exception as e:
        logging.error(f"Error logging data to CSV: {e}")

def normalize_url(url):
    if not url:  # If the URL is None or empty, return None directly
        return None
    return url.strip().rstrip('/').lower()

def main():
    meds_links = extract_links_from_csv_pandas('databases/meds.csv')
    sifted_links = extract_links_from_csv_pandas('databases/sifted.csv')
    scape_links = extract_links_from_csv_pandas('databases/scape.csv')
    llm_links = [normalize_url(entry['Link']) for entry in extract_links_from_csv_pandas('databases/llm.csv')]

    # Create a unique set of links, filtering out those already in llm_links
    combined_links = []
    all_links = meds_links + sifted_links + scape_links
    unique_links = {normalize_url(link['Link']): link for link in all_links if normalize_url(link['Link']) not in llm_links}
    combined_links = list(unique_links.values())

    if not combined_links:
        logging.info("No unique links to process. Exiting gracefully.")
        print("No unique links to process. Exiting gracefully.")
        return

    logging.info(f"Total unique links to process: {len(combined_links)}")

    for link_info in combined_links:
        log_entry = process_link(link_info, combined_links)
        if log_entry:
            log_to_csv_pandas(log_entry)

if __name__ == "__main__":
    main()
