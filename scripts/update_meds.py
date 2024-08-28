import requests
import csv
import os
import logging
from bs4 import BeautifulSoup

# Set up paths for CSV and log files
csv_folder = 'databases'
log_folder = 'logs'
csv_file_path = os.path.join(csv_folder, 'meds.csv')
log_file_path = os.path.join(log_folder, 'meds.log')

# Ensure directories exist
os.makedirs(csv_folder, exist_ok=True)
os.makedirs(log_folder, exist_ok=True)

# Set up logging
logging.basicConfig(filename=log_file_path, level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

logging.info('Meds Script started.')

# API request setup
url = 'https://sentry.azurewebsites.net/api/Feed/anonymous'
params = {
    'pageSize': 10,
    'pageNumber': 1
}

headers = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-IN,en;q=0.7',
    'Connection': 'keep-alive',
    'Origin': 'https://medsii.com',
    'Referer': 'https://medsii.com/',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'cross-site',
    'Sec-GPC': '1',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
    'sec-ch-ua': '"Not)A;Brand";v="99", "Brave";v="127", "Chromium";v="127"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"'
}

try:
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    data = response.json()
    logging.info('Data fetched successfully from API.')
except requests.exceptions.RequestException as e:
    logging.error(f"Failed to retrieve data: {e}")
    data = None

# Define CSV headers
headers = ["Title", "Time", "Link",  "Image URL", "Source Name",
           "Article Text", "Image URL Derived"]

# Function to parse bodyHTML and extract derived fields
def parse_body_html(body_html):
    soup = BeautifulSoup(body_html, 'html.parser')
    publish_timestamp = soup.find('p', id='publishTimeStamp').text if soup.find('p', id='publishTimeStamp') else ''
    article_text = ' '.join([p.text for p in soup.find_all('p', id='article')])
    image_url = soup.find('img', id='imageUri')['src'] if soup.find('img', id='imageUri') else ''
    source_link = soup.find('a', id='sourceURI')['href'] if soup.find('a', id='sourceURI') else ''
    return publish_timestamp, article_text, image_url, source_link

# Function to load existing data from CSV
def load_existing_data(csv_file):
    existing_entries = set()
    if os.path.exists(csv_file):
        with open(csv_file, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                # Create a tuple of fields that uniquely identify a row
                entry_key = (row["Title"], row["Link"])
                existing_entries.add(entry_key)
    return existing_entries

# Function to write data to the CSV
def write_data_to_csv(data, csv_file):
    if not data:
        logging.warning("No data to write to CSV.")
        return
    
    existing_entries = load_existing_data(csv_file)

    with open(csv_file, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=headers)

        # Iterate over each item in the data
        for item in data.get('data', []):
            try:
                title = item['itemData']['news']['headline']
                image_url = str(item['itemData']['news']['imageUri'])[:-9]
                source_name = item['itemData']['news']['sources']['name'][0]
                source_url = item['itemData']['news']['sources']['uri'][0]

                # Parse bodyHTML for derived data
                body_html = item['itemData']['news']['bodyHTML']
                publish_timestamp, article_text, image_url_derived, source_link = parse_body_html(body_html)

                # Create a tuple that uniquely identifies the row
                entry_key = (title, source_url)

                # Only write the row if it's not a duplicate
                if entry_key not in existing_entries:
                    writer.writerow({
                        "Time": publish_timestamp,
                        "Title": title,
                        "Link": source_url,
                        "Source Name": source_name,
                        "Article Text": article_text,
                        "Image URL": image_url,
                        "Image URL Derived": image_url_derived,
                    })
                    existing_entries.add(entry_key)
            except Exception as e:
                logging.error(f"Error processing article: {e}")
        logging.info(f"Successfully updated CSV.")

# Check if CSV file exists and write header if not
if not os.path.exists(csv_file_path):
    with open(csv_file_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        logging.info('CSV header written.')

# Write data to CSV
write_data_to_csv(data, csv_file_path)

logging.info('Meds script completed successfully.')
