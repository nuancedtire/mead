import requests
from bs4 import BeautifulSoup
import pandas as pd
import logging
from datetime import datetime
import os
from firebase_admin import credentials, firestore, initialize_app
import hashlib

def setup_logging():
    logging.basicConfig(filename='logs/digital_health_scraper.log', level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    logging.getLogger('').addHandler(console)

def setup_firebase():
    cred = credentials.Certificate("firebase_credentials.json")
    initialize_app(cred)
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

def parse_date_time(date_str, time_str):
    try:
        date_time_str = f"{date_str} {time_str}"
        return datetime.strptime(date_time_str, "%d %B %Y %I:%M %p")
    except ValueError as e:
        logging.warning(f"Error parsing date and time: {e}. Using current date and time.")
        return datetime.now()

def extract_digital_health_items(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    news_items = []

    articles = soup.find_all('article', class_='elementor-post')
    
    for article in articles:
        try:
            title_element = article.find('h3', class_='elementor-post__title')
            if not title_element or not title_element.find('a'):
                continue  # Skip this article if title or link is missing

            title = title_element.text.strip()
            link = title_element.find('a')['href']
            
            meta_data = article.find('div', class_='elementor-post__meta-data')
            if not meta_data:
                continue  # Skip this article if meta data is missing

            date_element = meta_data.find('span', class_='elementor-post-date')
            time_element = meta_data.find('span', class_='elementor-post-time')
            
            if not date_element or not time_element:
                continue  # Skip this article if date or time is missing

            date_str = date_element.text.strip()
            time_str = time_element.text.strip()
            
            date_time = parse_date_time(date_str, time_str)
            
            news_item = {
                'Title': title,
                'Link': link,
                'Time': date_time.strftime("%Y-%m-%d %H:%M:%S")
            }
            news_items.append(news_item)
            logging.info(f"Processed item: {title} - {date_time.strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception as e:
            logging.error(f"Error parsing article: {e}")

    logging.info(f"Total items processed: {len(news_items)}")
    return news_items

def save_to_firestore(data, db):
    combined_news_ref = db.collection('combined_news')
    batch = db.batch()
    
    for item in data:
        # Add 'Source' field to each item
        item['Source'] = 'Digital Health News'
        
        # Create a hash of the URL to use as the document ID
        doc_id = hashlib.md5(item['Link'].encode()).hexdigest()
        
        # Use the hash as the document ID
        doc_ref = combined_news_ref.document(doc_id)
        
        # Use set with merge=True to update existing documents or create new ones
        batch.set(doc_ref, item, merge=True)
    
    batch.commit()
    message = f"Data saved to Firestore. Total items: {len(data)}."
    logging.info(message)

def scrape_digital_health_news():
    setup_logging()
    db = setup_firebase()
    url = "https://www.digitalhealth.net/news/"  # Replace with the actual URL
    
    logging.info(f"Starting scrape for {url}")

    html_content = fetch_webpage(url)
    if html_content:
        news_items = extract_digital_health_items(html_content)
        if news_items:
            save_to_firestore(news_items, db)
        else:
            logging.info("No new items found.")
    else:
        logging.error("Failed to fetch webpage content.")

    logging.info("Scraping completed.")

if __name__ == "__main__":
    scrape_digital_health_news()