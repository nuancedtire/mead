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

# Set up logging
log_file_path = "logs/llm.log"
os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
logging.basicConfig(filename=log_file_path, level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Load configuration
model_name = config.llm_config['model_name']
system_message = config.llm_config['system_prompt']
hashtags = config.llm_config['hashtags']

# Retrieve the API key from the environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

client = OpenAI()

@retry(wait=wait_random_exponential(min=20, max=60), stop=stop_after_attempt(6))
def completion_with_backoff(**kwargs):
    """
    This function makes a request to the OpenAI API with exponential backoff 
    in case of failures. It retries the request up to 3 times.
    """
    return client.chat.completions.create(**kwargs)

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

def process_link(link_info):
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

    return generate_post(webpage_content, link, original_timestamp)

from pydantic import BaseModel, Field
from typing import List

# Define the data structure using Pydantic
class PostResponse(BaseModel):
    post_content: str = Field(..., description="The final generated post content based on the article.")
    hashtags: List[str] = Field(..., description="A list of relevant hashtags for the post.")

# Function definition
def generate_post(webpage_content, link, original_timestamp):
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
    if "Open navigation menu" in webpage_content:
      start_index = webpage_content.find("Open navigation menu")
      webpage_content = webpage_content[start_index:]
    try:
        response = completion_with_backoff(
            model=model_name,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": webpage_content}
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
                                "description": "The final generated post content based on the article. Ensure it is the post only and does not include any hashtags or images"
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
        data = PostResponse.parse_raw(full_response)
        llm_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        log_entry = [original_timestamp, llm_timestamp, data.post_content, data.hashtags, link, system_message, webpage_content, model_name]
        logging.info(f"Generated post for link {link}.")
        print(f"Generated post for link {link}.")
        return log_entry
    except Exception as e:
        logging.error(f"Error generating post: {e}")
        print(f"Error generating post: {e}")
        return None
def log_to_csv_pandas(log_entry, file_name="databases/llm-test.csv"):
    """
    Logs the generated post information to a CSV file.

    Args:
        log_entry (list): A list containing the log details.
        file_name (str): The name of the CSV file to log the entry to.
    """
    try:
        df_new = pd.DataFrame([log_entry], columns=["Time", "LLM Timestamp", "Post", "Hashtags", "Link", "Prompt", "Input", "Model"])

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

def main():
    """
    Main function that orchestrates the link processing by extracting links 
    from multiple CSV files, filtering unique links, and logging the results.
    """
    meds_links = extract_links_from_csv_pandas('databases/meds.csv')
    sifted_links = extract_links_from_csv_pandas('databases/sifted.csv')
    scape_links = extract_links_from_csv_pandas('databases/scape.csv')
    llm_links = [entry['Link'] for entry in extract_links_from_csv_pandas('databases/llm-test.csv')]
    
    combined_links = [link for link in meds_links + sifted_links + scape_links if link['Link'] not in llm_links]

    if not combined_links:
        logging.info("No unique links to process. Exiting gracefully.")
        print("No unique links to process. Exiting gracefully.")
        return

    logging.info(f"Total unique links to process: {len(combined_links)}")

    for link_info in combined_links:
        log_entry = process_link(link_info)
        if log_entry:
            log_to_csv_pandas(log_entry)

if __name__ == "__main__":
    main()
