import requests
from bs4 import BeautifulSoup
import pandas as pd
import logging
from datetime import datetime
import os

def setup_logging():
    logging.basicConfig(filename='logs/uktech_scraper.log', level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    logging.getLogger('').addHandler(console)

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

def parse_date(date_str):
    try:
        # Try parsing with day name (e.g., "Tue 3 Sep 2024")
        return datetime.strptime(date_str, "%a %d %b %Y")
    except ValueError:
        try:
            # Try parsing without day name (e.g., "3 Sep 2024")
            return datetime.strptime(date_str, "%d %b %Y")
        except ValueError as e:
            logging.warning(f"Error parsing date: {e}. Using current date.")
            return datetime.now()

def extract_uktech_items(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    news_items = []

    # Find the first article (different format)
    first_article = soup.find('div', class_='col-span-12 md:col-span-6 xl:col-span-4')
    if first_article:
        news_item = process_article(first_article, is_first=True)
        if news_item:
            news_items.append(news_item)
            logging.info("Processed first article")

    # Find the next two articles
    # other_articles = soup.find_all('h3', class_='flex justify-between gap-6 py-20')
    # logging.info(f"Found {len(other_articles)} additional articles")
    # for article in other_articles[:2]:  # Limit to 2 articles
    #     news_item = process_article(article, is_first=False)
    #     if news_item:
    #         news_items.append(news_item)
    #         logging.info("Processed additional article")

    # logging.info(f"Total items processed: {len(news_items)}")
    return news_items[:3]  # Ensure we return only the first 3 items

def process_article(article, is_first):
    try:
        if is_first:
            title_element = article.find('h3', class_='text-32 xl:text-40 text-green leading-[1.1]')
            link_element = article.find('a', href=True)
            date_element = article.find('time', class_='text-13 text-gray-400')
        else:
            title_element = article.find('h3', class_='text-18 sm:text-20 lg:text-24 text-green mt-7 leading-[1.2]')
            link_element = title_element.find('a') if title_element else None
            date_element = article.find('span', class_='text-11 text-gray-400')

        if not title_element or not link_element or not date_element:
            logging.warning(f"Missing elements in article: {article}")
            return None

        title = title_element.text.strip()
        link = link_element['href']
        date_str = date_element.text.strip()
        date_time = parse_date(date_str)

        news_item = {
            'Title': title,
            'Link': link,
            'Time': date_time.strftime("%Y-%m-%d %H:%M:%S")
        }
        logging.info(f"Processed item: {title} - {date_time.strftime('%Y-%m-%d %H:%M:%S')}")
        return news_item
    except Exception as e:
        logging.error(f"Error parsing article: {e}", exc_info=True)
        return None

def save_to_csv(data, filename):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    if os.path.exists(filename):
        existing_df = pd.read_csv(filename)
        new_df = pd.DataFrame(data)
        combined_df = pd.concat([existing_df, new_df]).drop_duplicates(subset=['Link'], keep='first')
    else:
        combined_df = pd.DataFrame(data)
    
    combined_df['Time'] = pd.to_datetime(combined_df['Time'], errors='coerce')
    combined_df = combined_df.sort_values('Time', ascending=False, na_position='last')
    
    combined_df.to_csv(filename, index=False)
    message = f"Data saved to {filename}. Total items: {len(combined_df)}."
    logging.info(message)

def scrape_uktech_news():
    setup_logging()
    url = "https://www.uktech.news/medtech"
    output_file = "databases/uktech_news.csv"
    
    logging.info(f"Starting scrape for {url}")

    try:
        html_content = fetch_webpage(url)
        if html_content:
            logging.info(f"Successfully fetched webpage. Content length: {len(html_content)}")
            
            news_items = extract_uktech_items(html_content)
            if news_items:
                save_to_csv(news_items, output_file)
            else:
                logging.info("No new items found.")
        else:
            logging.error("Failed to fetch webpage content.")
    except Exception as e:
        logging.error(f"An error occurred during scraping: {e}", exc_info=True)

    logging.info("Scraping completed.")

if __name__ == "__main__":
    scrape_uktech_news()