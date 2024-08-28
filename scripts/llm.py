import os
import csv
import logging
import requests
import pandas as pd
from datetime import datetime
from openai import OpenAI
import config
import openai
import json

# Set up logging
log_file_path = "logs/llm.log"
os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
logging.basicConfig(filename=log_file_path, level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Load configuration
model_name = config.llm_config['model_name']
system_message = config.llm_config['system_prompt']

# Retrieve the API key from the environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI client
client = OpenAI()

# Function to extract links from a CSV file using pandas
def extract_links_from_csv_pandas(file_path):
    try:
        if not os.path.exists(file_path):
            logging.warning(f"{file_path} does not exist, skipping...")
            print(f"{file_path} does not exist, skipping...")
            return []
        df = pd.read_csv(file_path)
        links = df['Link'].dropna().tolist()
        logging.info(f"Loaded {len(links)} links from {file_path}.")
        print(f"Loaded {len(links)} links from {file_path}.")
        return links
    except Exception as e:
        logging.error(f"Error reading {file_path}: {e}")
        print(f"Error reading {file_path}: {e}")
        return []

# Function to process each link
def process_link(link):
    try:
        url = f'http://r.jina.ai/{link}'
        response = requests.get(url)
        response.raise_for_status()
        webpage_content = response.text
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

    return generate_post(webpage_content, link)

# Function to generate post content using OpenAI
def generate_post(webpage_content, link):
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": webpage_content}
                ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "post_with_thumbnail",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "post_content": {
                                "type": "string",
                                "description": "The final generated post content based on the article."
                                },
                            "thumbnail_image_url": {
                                "type": "string",
                                "description": "The final URL of a relevant image from the article ready to be used as a thumbnail. If no image then reply None"
                                }
                            },
                    "required": [
                        "post_content",
                        "thumbnail_image_url"
                        ],
                        }
                    }
                }
            )
        full_response = response.choices[0].message.content
        data = json.loads(full_response)
        post = data['post_content']
        image = data['thumbnail_image_url']
        log_entry = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), post, image, link, system_message, webpage_content]
        logging.info(f"Generated post for link {link}.")
        print(f"Generated post for link {link}.")
        return log_entry
    except Exception as e:
        logging.error(f"Error generating post: {e}")
        print(f"Error generating post: {e}")
        return None

# Function to log results to a CSV file using pandas
def log_to_csv_pandas(log_entry, file_name="databases/llm.csv"):
    try:
        df_new = pd.DataFrame([log_entry], columns=["Timestamp", "Post", "Image", "Link", "Prompt", "Input"])
        if os.path.exists(file_name):
            df_existing = pd.read_csv(file_name)
            df_combined = pd.concat([df_existing, df_new]).drop_duplicates()
        else:
            df_combined = df_new

        df_combined.to_csv(file_name, index=False)
        logging.info(f"Logged data to {file_name}.")
        print(f"Logged data to {file_name}.")
    except Exception as e:
        logging.error(f"Error logging data to CSV: {e}")

def main():
  meds_links = extract_links_from_csv_pandas('databases/meds.csv')
  sifted_links = extract_links_from_csv_pandas('databases/sifted.csv')
  llm_links = extract_links_from_csv_pandas('databases/llm.csv')
  combined_links = set(meds_links + sifted_links) - set(llm_links)

  if not combined_links:
    logging.info("No unique links to process. Exiting gracefully.")
    print("No unique links to process. Exiting gracefully.")
    return

  logging.info(f"Total unique links to process: {len(combined_links)}")

  for link in combined_links:
    log_entry = process_link(link)
    if log_entry:
        log_to_csv_pandas(log_entry)

if __name__ == "__main__":
    main()
