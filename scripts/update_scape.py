import http.client
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import logging
import json
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
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import hashlib

# Set up logging
log_folder = 'logs'
log_file_path = os.path.join(log_folder, 'scape.log')
os.makedirs(log_folder, exist_ok=True)

# Set up logging
logging.basicConfig(filename=log_file_path,
                    level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Load configuration
small_model_name = config.llm_config["small_model"]
large_model_name = config.llm_config["large_model"]

# Initialize LLMs
small_llm = ChatOpenAI(model=small_model_name, temperature=0)
large_llm = ChatOpenAI(model=large_model_name, temperature=0)

# Firebase setup
cred = credentials.Certificate("firebase_credentials.json")
firebase_admin.initialize_app(cred)
db = firestore.client()


def setup_logging():
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


@retry(wait=wait_random_exponential(min=20, max=60),
       stop=stop_after_attempt(3))
def fetch_url_content(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching data from {url}: {e}")
        raise


def link_exists_in_firestore(link):
    doc_id = hashlib.md5(link.encode()).hexdigest()
    doc_ref = db.collection('combined_news').document(doc_id)
    return doc_ref.get().exists


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
    prompt = ChatPromptTemplate.from_messages([(
        "system",
        "You are an expert researcher. You will be given the web scraping of an article and you have to find the original source from which the article was written. Reply with `None` only if no appropriate link could be found. Please remember to reply only with link."
    ), ("human", "{webpage_content}")])

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
                logging.info(
                    f"Retrying to find source link (attempt {retry_count + 1})"
                )
                source_link = chain.invoke(
                    {"webpage_content": webpage_content})
            else:
                logging.warning(f"No source link found after 3 attempts")
                return link
    logging.warning(f"No source link found for {url}")
    return link


def process_medscape_data(data_dict):
    filtered_data = []
    for item in data_dict.get("data", []):
        if item["field_content_type"] in [
                "Clinical Summary", "Guidelines in Practice"
        ]:
            medscape_link = item["field_canonical_url"]

            logging.info(f"Processing item: {medscape_link}")

            # Check if the link already exists in Firestore
            if link_exists_in_firestore(medscape_link):
                logging.info(
                    f"Link already exists in Firestore, skipping: {medscape_link}"
                )
                continue  # Skip this item and move to the next one

            link = find_link(medscape_link)
            if link:
                filtered_data.append({
                    "Title":
                    item["field_engagement_title"],
                    "Time":
                    standardize_time(item["field_date_publish"]),
                    "Link":
                    medscape_link,
                    "Source Link":
                    link,
                    "Teaser":
                    item["field_engagement_teaser"],
                    "Image URL":
                    item["field_asset_thumbnail"],
                    "Content Type":
                    item["field_content_type"],
                    "Source":
                    "Medscape"
                })
    return filtered_data


def save_to_firestore(data):
    if not data:
        logging.info("No new data to update.")
        return

    batch = db.batch()
    combined_news_ref = db.collection('combined_news')

    for item in data:
        doc_id = hashlib.md5(item['Link'].encode()).hexdigest()
        doc_ref = combined_news_ref.document(doc_id)
        batch.set(doc_ref, item, merge=True)

    batch.commit()
    logging.info(f"Successfully updated Firestore with {len(data)} items.")


def main():
    setup_logging()
    logging.info('Medscape script started.')

    try:
        # Establish a connection
        conn = http.client.HTTPSConnection("www.medscape.co.uk")
        logging.info('Connection to Medscape established.')

        # Parameters for the request
        page = "1"
        limit = "50"

        # Headers for the request
        headers = {
            'priority':
            "u=1, i",
            'referer':
            "https://www.medscape.co.uk/",
            'sec-ch-ua':
            "\"Not)A;Brand\";v=\"99\", \"Brave\";v=\"127\", \"Chromium\";v=\"127\"",
            'sec-ch-ua-mobile':
            "?0",
            'sec-ch-ua-platform':
            "\"macOS\"",
            'sec-fetch-dest':
            "empty",
            'sec-fetch-mode':
            "cors",
            'sec-fetch-site':
            "same-origin",
            'sec-gpc':
            "1",
            'user-agent':
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
        }

        # Make the GET request
        conn.request(
            "GET",
            f"/api/rec-engine/api/v1/content_feed?aud=uk_web&page={page}&limit={limit}",
            headers=headers)
        logging.info('Request sent to Medscape API.')

        # Get the response
        res = conn.getresponse()
        data = res.read()
        logging.info('Response received from Medscape API.')

        # Decode the response into a Python dictionary
        data_dict = json.loads(data.decode("utf-8"))
        logging.info('Response data decoded into dictionary.')

        # Process the Medscape data
        filtered_data = process_medscape_data(data_dict)

        # Save data to Firestore
        save_to_firestore(filtered_data)

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise

    logging.info('Medscape script completed.')


if __name__ == "__main__":
    main()
