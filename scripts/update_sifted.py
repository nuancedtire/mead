import requests
import re
import pandas as pd
import os
import logging
from datetime import datetime

# Define paths for the CSV and log files
csv_folder = 'databases'
log_folder = 'logs'
csv_file_path = os.path.join(csv_folder, 'sifted.csv')
log_file_path = os.path.join(log_folder, 'sifted.log')

# Ensure directories exist
os.makedirs(csv_folder, exist_ok=True)
os.makedirs(log_folder, exist_ok=True)

# Set up logging
logging.basicConfig(filename=log_file_path, level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

logging.info('Sifted script started.')

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

# Prepare data for DataFrame
titles = [title for title, link in links_titles]
links = [link for title, link in links_titles]

# Create a DataFrame with the new data
new_data = pd.DataFrame({
    "Title": titles,
    "Time": dates,
    "Link": links
})

new_data = new_data[:5]

# Check if the CSV file already exists
try:
    if os.path.exists(csv_file_path):
        # Load the existing data
        existing_data = pd.read_csv(csv_file_path)
        logging.info('Existing CSV file loaded.')

        # Concatenate the old and new data, ensuring no duplicates
        combined_data = pd.concat([new_data, existing_data]).drop_duplicates(subset=["Title", "Time", "Link"])

        # Sort by time to ensure the latest entries are at the top
        combined_data.sort_values(by="Time", ascending=False, inplace=True)
    else:
        # If the CSV does not exist, use the new data as the combined data
        combined_data = new_data
        logging.info('No existing CSV file found. Creating new CSV.')

    # Save the updated data back to the CSV file
    combined_data.to_csv(csv_file_path, index=False)
    logging.info(f"Data saved to {csv_file_path}")
except Exception as e:
    logging.error(f"Error processing or saving the CSV file: {e}")

logging.info('Sifted script completed.')
