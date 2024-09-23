import requests
from bs4 import BeautifulSoup
import pandas as pd
import logging
from datetime import datetime
import os

def setup_logging():
    logging.basicConfig(filename='logs/nice.log', level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')
    # Also print to console
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    logging.getLogger('').addHandler(console)

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
        return datetime.strptime(date_string, "%d %B %Y").strftime("%Y-%m-%d")
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
            news_items.append({
                'Title': title,
                'Link': link,
                'Time': parse_date(date)
            })
        except AttributeError as e:
            logging.error(f"Error parsing article: {e}")

    return news_items

def load_existing_data(filename):
    if os.path.exists(filename):
        return pd.read_csv(filename)
    return pd.DataFrame(columns=['Title', 'Link', 'Time'])

def save_to_csv(data, filename):
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    # Load existing data if file exists, otherwise create new DataFrame
    if os.path.exists(filename):
        existing_df = pd.read_csv(filename)
        new_df = pd.DataFrame(data)
        combined_df = pd.concat([existing_df, new_df]).drop_duplicates(subset=['Link'], keep='first')
    else:
        combined_df = pd.DataFrame(data)
    
    # Sort by date, most recent first
    combined_df['Time'] = pd.to_datetime(combined_df['Time'])
    combined_df = combined_df.sort_values('Time', ascending=False)
    
    # Save to CSV
    combined_df.to_csv(filename, index=False)
    logging.info(f"Data saved to {filename}. Total items: {len(combined_df)}.")
    print(f"Data saved to {filename}. Total items: {len(combined_df)}.")
    
def scrape_nice_news():
    setup_logging()
    url = "https://www.nice.org.uk/news/articles"
    output_file = "databases/nice.csv"
    
    logging.info(f"Starting scrape for {url}")

    html_content = fetch_webpage(url)
    if html_content:
        new_items = extract_nice_news_links(html_content)
        if new_items:
            save_to_csv(new_items, output_file)
        else:
            logging.info("No new items found.")
    else:
        logging.error("Failed to fetch webpage content.")

if __name__ == "__main__":
    scrape_nice_news()