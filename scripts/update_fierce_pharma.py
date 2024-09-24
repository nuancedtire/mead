import requests
import pandas as pd
import logging
from datetime import datetime
import os

def setup_logging():
    logging.basicConfig(filename='logs/fierce_pharma.log', level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)

def fetch_api_data(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Error fetching {url}: {e}")
        return None

def extract_uuids(api_data):
    articles = api_data.get('articles', [])
    uuids = [article['uuid'] for article in articles if 'uuid' in article]
    logging.info(f"Extracted {len(uuids)} UUIDs")
    return uuids

def extract_article_data(article_json):
    data = article_json.get('data', {})
    attributes = data.get('attributes', {})
    
    title = attributes.get('title')
    path = attributes.get('path', {})
    alias = path.get('alias', '')
    
    if not alias.startswith('/pharma'):
        logging.info(f"Skipped article: {title[:50]}... (alias: {alias[:30]}...)")
        return None
    
    link = f"https://www.fiercepharma.com{alias}"
    published_date = attributes.get('field_date_published')
    
    if published_date:
        date = datetime.fromisoformat(published_date.replace('Z', '+00:00'))
        formatted_date = date.strftime("%Y-%m-%d %H:%M:%S")
    else:
        formatted_date = None
    
    return {
        'Title': title,
        'Link': link,
        'Time': formatted_date
    }

def scrape_fierce_pharma():
    setup_logging()
    base_url = "https://www.fiercepharma.com/api/v1/fronts/104751?page="
    article_base_url = "https://www.fiercepharma.com/jsonapi/node/article/"
    output_file = "databases/fierce_pharma.csv"
    
    logging.info("Starting scrape for Fierce Pharma")

    all_articles = []
    for page in range(1, 3):  # Scrape first 2 pages
        logging.info(f"Fetching data from page {page}")
        api_data = fetch_api_data(f"{base_url}{page}")
        if api_data:
            uuids = extract_uuids(api_data)
            for uuid in uuids:
                article_data = fetch_api_data(f"{article_base_url}{uuid}")
                if article_data:
                    article_info = extract_article_data(article_data)
                    if article_info:
                        all_articles.append(article_info)
                        logging.info(f"Processed article: {article_info['Title'][:50]}...")
                else:
                    logging.error(f"Failed to fetch article data for UUID: {uuid}")
        else:
            logging.error(f"Failed to fetch data from page {page}")

    if all_articles:
        save_to_csv(all_articles, output_file)
        logging.info(f"Saved {len(all_articles)} articles to CSV.")
    else:
        logging.warning("No articles found.")

    logging.info("Scraping completed.")

def save_to_csv(data, filename):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    if os.path.exists(filename):
        existing_df = pd.read_csv(filename)
        new_df = pd.DataFrame(data)
        combined_df = pd.concat([existing_df, new_df]).drop_duplicates(subset=['Link'], keep='first')
    else:
        combined_df = pd.DataFrame(data)
    
    combined_df['Time'] = pd.to_datetime(combined_df['Time'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
    combined_df = combined_df.sort_values('Time', ascending=False, na_position='last')
    
    combined_df.to_csv(filename, index=False, date_format='%Y-%m-%d %H:%M:%S')
    logging.info(f"Data saved to {filename}. Total items: {len(combined_df)}.")

if __name__ == "__main__":
    scrape_fierce_pharma()
