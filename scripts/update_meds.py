import requests
import os
import logging
from bs4 import BeautifulSoup
from datetime import datetime
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import hashlib

# Set up logging
log_folder = 'logs'
log_file_path = os.path.join(log_folder, 'meds.log')
os.makedirs(log_folder, exist_ok=True)
logging.basicConfig(filename=log_file_path, level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

logging.info('Medsii Script started.')

# Firebase setup
cred = credentials.Certificate("firebase_credentials.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

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
    print('Data fetched successfully from API.')
except requests.exceptions.RequestException as e:
    logging.error(f"Failed to retrieve data: {e}")
    print(f"Failed to retrieve data: {e}")
    data = None

def parse_body_html(body_html):
    soup = BeautifulSoup(body_html, 'html.parser')
    publish_timestamp = soup.find('p', id='publishTimeStamp').text if soup.find('p', id='publishTimeStamp') else ''
    article_text = ' '.join([p.text for p in soup.find_all('p', id='article')])
    image_url = soup.find('img', id='imageUri')['src'] if soup.find('img', id='imageUri') else ''
    source_link = soup.find('a', id='sourceURI')['href'] if soup.find('a', id='sourceURI') else ''
    return publish_timestamp, article_text, image_url, source_link

def standardize_time(time_str):
    try:
        dt = datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        try:
            dt = datetime.strptime(time_str, "%b %d, %Y, %I:%M %p")
        except ValueError:
            logging.warning(f"Failed to standardize time format for {time_str}")
            print(f"Failed to standardize time format for {time_str}")
            return time_str
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def save_to_firestore(data):
    if not data:
        logging.warning("No data to write to Firestore.")
        print("No data to write to Firestore.")
        return
    
    combined_news_ref = db.collection('combined_news')
    batch = db.batch()
    new_items_count = 0

    for item in data.get('data', []):
        try:
            title = item['itemData']['news']['headline']
            image_url = str(item['itemData']['news']['imageUri'])[:-9]
            source_name = item['itemData']['news']['sources']['name'][0]
            source_url = item['itemData']['news']['sources']['uri'][0]

            body_html = item['itemData']['news']['bodyHTML']
            publish_timestamp, article_text, _, source_link = parse_body_html(body_html)
            publish_timestamp = standardize_time(publish_timestamp)

            doc_id = hashlib.md5(source_url.encode()).hexdigest()
            doc_ref = combined_news_ref.document(doc_id)

            new_data = {
                "Title": title,
                "Time": publish_timestamp,
                "Link": source_url,
                "Image URL": image_url,
                "Teaser": article_text,
                "Source Name": source_name,
                "Source": "Medsii"
            }

            batch.set(doc_ref, new_data, merge=True)
            new_items_count += 1

        except Exception as e:
            logging.error(f"Error processing article: {e}")
            print(f"Error processing article: {e}")

    batch.commit()
    logging.info(f"Successfully updated Firestore with {new_items_count} new items.")
    print(f"Successfully updated Firestore with {new_items_count} new items.")

# Save data to Firestore
save_to_firestore(data)

logging.info('Medsii script completed successfully.')