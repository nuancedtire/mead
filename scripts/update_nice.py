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
    logging.basicConfig(filename='logs/nice.log', level=logging.INFO,
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
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15',
            'Accept-Language': 'en-GB,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cookie': 'ASP.NET_SessionId=1j1ujbtqljodbfqqpcy4w0pa; ud=%7B%7D'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logging.error(f"Error fetching {url}: {e}")
        return None

def parse_date(date_string):
    try:
        parsed_date = datetime.strptime(date_string, "%d %B %Y").replace(hour=0, minute=0, second=0)
        formatted_date = parsed_date.strftime("%Y-%m-%d %H:%M:%S")
        return formatted_date
    except ValueError:
        logging.error(f"Error parsing date: {date_string}")
        return date_string

def extract_nice_news_links(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    news_items = []

    articles = soup.find_all('article', class_=['FeaturedStory_story__9p_lI', 'NewsCard_newsCard__kP3m6'])
    
    for article in articles:
        try:
            title = article.find('h3').text.strip()
            link = 'https://www.nice.org.uk' + article.find('a')['href']
            date = article.find('time').text.strip()
            parsed_date = parse_date(date)
            news_items.append({
                'Title': title,
                'Link': link,
                'Time': parsed_date,
                'Source': 'NICE'
            })
        except AttributeError as e:
            logging.error(f"Error parsing article: {e}")

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
    
def scrape_nice_news():
    setup_logging()
    db = setup_firebase()
    url = "https://www.nice.org.uk/news/articles"
    
    logging.info(f"Starting scrape for {url}")

    html_content = fetch_webpage(url)
    if html_content:
        new_items = extract_nice_news_links(html_content)
        if new_items:
            save_to_firestore(new_items, db)
        else:
            logging.info("No new items found.")
    else:
        logging.error("Failed to fetch webpage content.")

if __name__ == "__main__":
    scrape_nice_news()