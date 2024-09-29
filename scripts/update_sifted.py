import requests
import re
import os
import logging
from datetime import datetime
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import hashlib

# Define paths for the log file
log_folder = 'logs'
log_file_path = os.path.join(log_folder, 'sifted.log')

# Ensure directory exists
os.makedirs(log_folder, exist_ok=True)

# Set up logging
logging.basicConfig(filename=log_file_path, level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

logging.info('Sifted script started.')

# Firebase setup
cred = credentials.Certificate("firebase_credentials.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

url = 'https://r.jina.ai/sifted.eu/sector/healthtech/'

# Fetch the webpage content
try:
    sifted = requests.get(url)
    sifted.raise_for_status()
    webpage_content = sifted.text
    logging.info('Successfully fetched data from URL.')
except requests.exceptions.HTTPError as errh:
    logging.error(f"HTTP Error: {errh}")
except requests.exceptions.ConnectionError as errc:
    logging.error(f"Error Connecting: {errc}")
except requests.exceptions.Timeout as errt:
    logging.error(f"Timeout Error: {errt}")
except requests.exceptions.RequestException as err:
    logging.error(f"Unexpected Error: {err}")
    webpage_content = ""
    
# Phrase to search for
search_phrase = "Open navigation menu"

# Find the position of the search phrase and trim everything before it
start_index = webpage_content.find(search_phrase)

if start_index != -1:
    trimmed_content = webpage_content[start_index:]
    logging.info('Search phrase found and content trimmed.')
else:
    trimmed_content = webpage_content  # If the phrase is not found, keep the original content
    logging.warning('Search phrase not found. Using original content.')

# Regular expression patterns to match the titles, links, and dates
link_pattern = re.compile(r'\[(.*?)\]\((https://sifted\.eu/articles/.*?)\)')
date_pattern = re.compile(r'(\w+\s\d{1,2},\s\d{4})')

# Find all matches for links and titles
links_titles = link_pattern.findall(trimmed_content)
# Find all matches for dates
dates = date_pattern.findall(trimmed_content)

if not links_titles or not dates:
    logging.warning("No titles, links, or dates found in the content. Possible webpage structure change.")

# Function to standardize time format
def standardize_time(time_str):
    try:
        # Parse the format 'Month DD, YYYY' and standardize it to 'YYYY-MM-DD 00:00:00'
        dt = datetime.strptime(time_str, "%B %d, %Y")
        return dt.strftime("%Y-%m-%d 00:00:00")
    except ValueError:
        logging.warning(f"Failed to standardize time format for {time_str}")
        return time_str  # Return the original string if parsing fails

# Standardize all dates
dates = [standardize_time(date) for date in dates]

# Ensure all lists have the same length - trim to the shortest length
min_length = min(len(links_titles), len(dates))
links_titles = links_titles[:min_length]
dates = dates[:min_length]

# Prepare data for Firestore
new_data = []
for (title, link), date in zip(links_titles, dates):
    new_data.append({
        "Title": title,
        "Time": date,
        "Link": link,
        "Source": "Sifted"
    })

new_data = new_data[:5]  # Limit to 5 items

# Save to Firestore
def save_to_firestore(data):
    batch = db.batch()
    combined_news_ref = db.collection('combined_news')

    for item in data:
        doc_id = hashlib.md5(item['Link'].encode()).hexdigest()
        doc_ref = combined_news_ref.document(doc_id)
        batch.set(doc_ref, item, merge=True)

    batch.commit()
    logging.info(f"Data saved to Firestore. Total items: {len(data)}.")

try:
    save_to_firestore(new_data)
except Exception as e:
    logging.error(f"Error saving data to Firestore: {e}")

logging.info('Sifted script completed.')