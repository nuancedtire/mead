import http.client
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import logging
import json
import pandas as pd
import requests
from datetime import datetime
from dateutil import parser
from urllib.parse import urlparse
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
)
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# Define paths for the CSV and log files
csv_folder = 'databases'
log_folder = 'logs'
csv_file_path = os.path.join(csv_folder, 'scape.csv')
log_file_path = os.path.join(log_folder, 'scape.log')

# Ensure directories exist
os.makedirs(csv_folder, exist_ok=True)
os.makedirs(log_folder, exist_ok=True)

# Load configuration
small_model_name = config.llm_config["small_model"]
large_model_name = config.llm_config["large_model"]

# Initialize LLMs
small_llm = ChatOpenAI(model=small_model_name, temperature=0)
large_llm = ChatOpenAI(model=large_model_name, temperature=0)

def setup_logging():
    logging.basicConfig(filename=log_file_path, level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')
    # Also print to console
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    logging.getLogger('').addHandler(console)

# Function to standardize time format
def standardize_time(time_str):
    try:
        dt = parser.parse(time_str)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        logging.warning(f"Failed to standardize time format for {time_str}")
        return time_str

@retry(wait=wait_random_exponential(min=20, max=60), stop=stop_after_attempt(3))
def fetch_url_content(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching data from {url}: {e}")
        raise

def find_link(link):
    parsed_url = urlparse(link)
    netloc = parsed_url.netloc
    if netloc.startswith("www."):
        netloc = netloc[4:]
    stripped_link = f"{netloc}{parsed_url.path}"
    url = f'http://r.jina.ai/{stripped_link}'
    
    logging.info(f"Fetching URL: {url}")
    webpage_content = fetch_url_content(url)
    
    # Define the prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert researcher. You will be given the web scraping of an article and you have to find the original source from which the article was written. Reply with `None` only if no appropriate link could be found. Please remember to reply only with link."),
        ("human", "{webpage_content}")
    ])
    
    # Create the chain
    chain = prompt | large_llm | StrOutputParser()
    
    # Execute the chain
    source_link = chain.invoke({"webpage_content": webpage_content})
    
    retry_count = 0
    while retry_count < 3:
        if source_link.lower() != "none":
            logging.info(f"Found source link: {source_link}")
            return source_link
        else:
            retry_count += 1
            if retry_count < 3:
                logging.info(f"Retrying to find source link (attempt {retry_count + 1})")
                source_link = chain.invoke({"webpage_content": webpage_content})
            else:
                logging.warning(f"No source link found after 3 attempts")
                return link
        logging.warning(f"No source link found for {url}")
        return link

def process_medscape_data(data_dict, existing_links):
    filtered_data = []
    for item in data_dict.get("data", []):
        if item["field_content_type"] in ["Clinical Summary", "Guidelines in Practice"]:
            medscape_link = item["field_canonical_url"]
            
            # Check if the Medscape link already exists in our CSV
            if medscape_link in existing_links:
                logging.info(f"Skipping existing link: {medscape_link}")
                continue
            
            logging.info(f"Processing new item: {medscape_link}")
            # Only call find_link if it's a new Medscape link
            link = find_link(medscape_link)
            if link:
                filtered_data.append({
                    "Title": item["field_engagement_title"],
                    "Time": standardize_time(item["field_date_publish"]),
                    "Link": medscape_link,
                    "Source Link": link,
                    "Teaser": item["field_engagement_teaser"],
                    "Image URL": item["field_asset_thumbnail"],
                    "Content Type": item["field_content_type"]
                })
    return filtered_data

def main():
    setup_logging()
    logging.info('Medscape script started.')

    try:
        # Load existing data if the CSV file exists
        if os.path.exists(csv_file_path):
            existing_df = pd.read_csv(csv_file_path)
            existing_links = set(existing_df['Link'].tolist())
            logging.info('Existing CSV file loaded.')
        else:
            existing_df = pd.DataFrame()
            existing_links = set()
            logging.info('No existing CSV file found. Creating new data structure.')

        # Establish a connection
        conn = http.client.HTTPSConnection("www.medscape.co.uk")
        logging.info('Connection to Medscape established.')

        # Parameters for the request
        page = "1"
        limit = "50"

        # Headers for the request
        headers = {
            'priority': "u=1, i",
            'referer': "https://www.medscape.co.uk/",
            'sec-ch-ua': "\"Not)A;Brand\";v=\"99\", \"Brave\";v=\"127\", \"Chromium\";v=\"127\"",
            'sec-ch-ua-mobile': "?0",
            'sec-ch-ua-platform': "\"macOS\"",
            'sec-fetch-dest': "empty",
            'sec-fetch-mode': "cors",
            'sec-fetch-site': "same-origin",
            'sec-gpc': "1",
            'user-agent': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
        }

        # Make the GET request
        conn.request("GET", f"/api/rec-engine/api/v1/content_feed?aud=uk_web&page={page}&limit={limit}", headers=headers)
        logging.info('Request sent to Medscape API.')

        # Get the response
        res = conn.getresponse()
        data = res.read()
        logging.info('Response received from Medscape API.')

        # Decode the response into a Python dictionary
        data_dict = json.loads(data.decode("utf-8"))
        logging.info('Response data decoded into dictionary.')
        
        # Process the Medscape data
        filtered_data = process_medscape_data(data_dict, existing_links)

        # If new data is found, append it to the existing data
        if filtered_data:
            new_df = pd.DataFrame(filtered_data)
            updated_df = pd.concat([existing_df, new_df], ignore_index=True)
            updated_df.to_csv(csv_file_path, index=False)
            logging.info(f"CSV file updated with {len(filtered_data)} new items. Total items: {len(updated_df)}.")
        else:
            logging.info("No new links found, CSV file is up to date.")

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise

    logging.info('Medscape script completed.')

if __name__ == "__main__":
    main()
