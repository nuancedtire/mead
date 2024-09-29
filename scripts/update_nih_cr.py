import requests
from bs4 import BeautifulSoup
import logging
from datetime import datetime
import os
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import hashlib

def setup_logging():
    logging.basicConfig(filename='logs/nih_clinical_research.log', level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    logging.getLogger('').addHandler(console)

def setup_firebase():
    cred = credentials.Certificate("firebase_credentials.json")
    firebase_admin.initialize_app(cred)
    return firestore.client()

def fetch_webpage(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logging.error(f"Error fetching {url}: {e}")
        return None

def parse_date(date_string):
    date_formats = [
        "%B %d, %Y",
        "%A, %B %d, %Y"
    ]
    
    for date_format in date_formats:
        try:
            return datetime.strptime(date_string, date_format)
        except ValueError:
            continue
    
    logging.warning(f"Could not parse date: {date_string}. Using current date.")
    return datetime.now()

def extract_nih_news_items(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    news_items = []
    current_year = datetime.now().year

    teasers = soup.find_all('div', class_='teaser-clickable')
    
    for teaser in teasers[:5]:  # Only process the first 5 teasers
        try:
            title_element = teaser.find('h4', class_='teaser-title')
            title = title_element.text.strip()
            link = title_element.find('a')['href']
            
            if not link.startswith('http'):
                link = 'https://www.nih.gov' + link
            
            description = teaser.find('p', class_='teaser-description').text.strip()
            date_str = description.split('—')[0].strip()
            date = parse_date(date_str)
            
            if date.year != current_year:
                continue
            
            img_element = teaser.find('img', class_='media-element')
            image_url = img_element['src'] if img_element else ''
            image_url = image_url.split('?')[0] if image_url else ''
            
            news_item = {
                'Title': title,
                'Link': link,
                'Description': description,
                'Time': date.strftime("%Y-%m-%d"),
                'ImageURL': image_url,
                'Source': 'NIH Clinical Research'
            }
            news_items.append(news_item)
            logging.info(f"Processed item: {title} - {date.strftime('%Y-%m-%d')}")
        except Exception as e:
            logging.error(f"Error parsing teaser: {e}")

    logging.info(f"Total items processed: {len(news_items)}")
    return news_items
def save_to_firestore(data, db):
    combined_news_ref = db.collection('combined_news')
    batch = db.batch()
    
    for item in data:
        doc_id = hashlib.md5(item['Link'].encode()).hexdigest()
        doc_ref = combined_news_ref.document(doc_id)
        batch.set(doc_ref, item, merge=True)
    
    batch.commit()
    logging.info(f"Data saved to Firestore. Total items: {len(data)}.")

def scrape_nih_clinical_research_news():
    setup_logging()
    db = setup_firebase()
    url = "https://www.nih.gov/health-information/nih-clinical-research-trials-you/news"
    
    logging.info(f"Starting scrape for {url}")

    html_content = fetch_webpage(url)
    if html_content:
        news_items = extract_nih_news_items(html_content)
        if news_items:
            save_to_firestore(news_items, db)
        else:
            logging.info("No new items found.")
    else:
        logging.error("Failed to fetch webpage content.")

    logging.info("Scraping completed.")

if __name__ == "__main__":
    scrape_nih_clinical_research_news()