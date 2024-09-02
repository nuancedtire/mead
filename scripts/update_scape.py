import http.client
import json
import os
import pandas as pd
from datetime import datetime
import requests
import openai
from openai import OpenAI
from urllib.parse import urlparse
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
)  # for exponential backoff
import time
import logging
from dateutil import parser

# Define paths for the CSV and log files
csv_folder = 'databases'
log_folder = 'logs'
csv_file_path = os.path.join(csv_folder, 'scape.csv')
log_file_path = os.path.join(log_folder, 'scape.log')

# Ensure directories exist
os.makedirs(csv_folder, exist_ok=True)
os.makedirs(log_folder, exist_ok=True)

# Set up logging
logging.basicConfig(filename=log_file_path, level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

logging.info('Medscape script started.')

try:
    # Establish a connection
    conn = http.client.HTTPSConnection("www.medscape.co.uk")
    logging.info('Connection to Medscape established.')
    print('Connection to Medscape established.')

    # Parameters for the request
    page = "1"
    limit = "20"

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
    print('Request sent to Medscape API.')

    # Get the response
    res = conn.getresponse()
    data = res.read()
    logging.info('Response received from Medscape API.')
    print('Response received from Medscape API.')

    # Decode the response into a Python dictionary
    data_dict = json.loads(data.decode("utf-8"))
    logging.info('Response data decoded into dictionary.')
    print('Response data decoded into dictionary.')
    
except Exception as e:
    logging.error(f"An error occurred during the connection or data fetching: {e}")
    print(f"An error occurred during the connection or data fetching: {e}")
    raise

# Function to standardize time format
def standardize_time(time_str):
    try:
        # Parse the time string, which automatically handles various formats including timezones
        dt = parser.parse(time_str)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        logging.warning(f"Failed to standardize time format for {time_str}")
        print(f"Failed to standardize time format for {time_str}")
        return time_str

@retry(wait=wait_random_exponential(min=20, max=60), stop=stop_after_attempt(3))
def call_openai_with_backoff(client, webpage_content):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert researcher. You will be given the web scraping of an article and you have to find the original source other than Medscape from which the article was written. Reply only with link. Reply with the medscape link itself if no appropriate link could be found.",
                },
                {
                    "role": "user",
                    "content": webpage_content,
                }
            ],
            temperature=0,
            max_tokens=256,
        )
        logging.info("Received response from OpenAI API.")
        print("Received response from OpenAI API.")
        return response
    except Exception as e:
        logging.error(f"An error occurred while calling the OpenAI API: {e}")
        print(f"An error occurred while calling the OpenAI API: {e}")
        raise

def find_link(link):
    parsed_url = urlparse(link)
    netloc = parsed_url.netloc
    if netloc.startswith("www."):
        netloc = netloc[4:]
    stripped_link = f"{netloc}{parsed_url.path}"

    url = f'http://r.jina.ai/{stripped_link}'
    logging.info(f"Fetching URL: {url}")
    print(f"Fetching URL: {url}")
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        webpage_content = response.text
        logging.info(f"Successfully fetched data from {url}.")
        print(f"Successfully fetched data from {url}.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching data from {url}: {e}")
        print(f"Error fetching data from {url}: {e}")
        return None

    client = OpenAI()

    retries = 3
    for attempt in range(retries):
        try:
            found_src = call_openai_with_backoff(client, webpage_content)
            source_link = found_src.choices[0].message.content

            if source_link.lower() != "none":
                logging.info(f"Attempt {attempt + 1} succeeded with link: {source_link}")
                print(f"Attempt {attempt + 1} succeeded with link: {source_link}")
                return source_link
            else:
                logging.warning(f"Attempt {attempt + 1} failed for {url}, retrying...")
                print(f"Attempt {attempt + 1} failed for {url}, retrying...")
        except Exception as e:
            logging.error(f"An error occurred on attempt {attempt + 1} for url: {e}")
            print(f"An error occurred on attempt {attempt + 1} for url: {e}")

    logging.error(f"All attempts failed for {url}. Returning None.")
    print(f"All attempts failed for {url}. Returning None.")
    return None

# Load existing data if the CSV file exists
if os.path.exists(csv_file_path):
    existing_df = pd.read_csv(csv_file_path)
    existing_links = set(existing_df['Medscape Link'].tolist())
    logging.info('Existing CSV file loaded.')
    print('Existing CSV file loaded.')
else:
    existing_df = pd.DataFrame()
    existing_links = set()
    logging.info('No existing CSV file found. Creating new data structure.')
    print('No existing CSV file found. Creating new data structure.')

# Filter and process new data
filtered_data = []
for item in data_dict.get("data", []):
    if item["field_content_type"] in ["Clinical Summary", "Guidelines in Practice"]:
        medscape_link = item["field_canonical_url"]
        if medscape_link not in existing_links:
            logging.info(f"Processing new item: {medscape_link}")
            print(f"Processing new item: {medscape_link}")
            link = find_link(medscape_link)
            if link:
                filtered_data.append({
                    "Title": item["field_engagement_title"],
                    "Time": standardize_time(item["field_date_publish"]),
                    "Link": link,
                    "Medscape Link": medscape_link,
                    "Teaser": item["field_engagement_teaser"],
                    "Image URL": item["field_asset_thumbnail"],
                    "Content Type": item["field_content_type"]
                })

# If new data is found, append it to the existing data
if filtered_data:
    new_df = pd.DataFrame(filtered_data)
    updated_df = pd.concat([existing_df, new_df], ignore_index=True)
    updated_df.to_csv(csv_file_path, index=False)
    logging.info("CSV file updated with new data.")
    print("CSV file updated with new data.")
else:
    logging.info("No new links found, CSV file is up to date.")
    print("No new links found, CSV file is up to date.")

logging.info('Medscape script completed.')
print('Medscape script completed.')
