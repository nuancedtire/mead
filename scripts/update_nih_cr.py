import requests
from bs4 import BeautifulSoup
import pandas as pd
import logging
from datetime import datetime, timedelta
import os

def setup_logging():
    logging.basicConfig(filename='logs/nih_clinical_research.log', level=logging.INFO,
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
    return datetime.now()  # Return current date as fallback

def extract_nih_news_items(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    news_items = []
    current_year = datetime.now().year

    teasers = soup.find_all('div', class_='teaser-clickable')
    
    for teaser in teasers:
        try:
            title_element = teaser.find('h4', class_='teaser-title')
            title = title_element.text.strip()
            link = title_element.find('a')['href']
            
            # Ensure the link is a full URL
            if not link.startswith('http'):
                link = 'https://www.nih.gov' + link
            
            description = teaser.find('p', class_='teaser-description').text.strip()
            date_str = description.split('—')[0].strip()
            date = parse_date(date_str)
            
            # Skip if the post is not from the current year
            if date.year != current_year:
                continue
            
            # Extract image URL
            img_element = teaser.find('img', class_='media-element')
            image_url = img_element['src'] if img_element else ''
            
            # Remove query parameters from image URL
            image_url = image_url.split('?')[0] if image_url else ''
            
            news_item = {
                'Title': title,
                'Link': link,
                'Description': description,
                'Time': date.strftime("%Y-%m-%d"),
                'ImageURL': image_url
            }
            news_items.append(news_item)
            logging.info(f"Processed item: {title} - {date.strftime('%Y-%m-%d')}")
        except Exception as e:
            logging.error(f"Error parsing teaser: {e}")

    logging.info(f"Total items processed: {len(news_items)}")
    return news_items

def save_to_csv(data, filename):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    if os.path.exists(filename):
        existing_df = pd.read_csv(filename)
        new_df = pd.DataFrame(data)
        combined_df = pd.concat([existing_df, new_df]).drop_duplicates(subset=['Link'], keep='first')
    else:
        combined_df = pd.DataFrame(data)
    
    # Convert 'Time' to datetime, coercing errors to NaT
    combined_df['Time'] = pd.to_datetime(combined_df['Time'], errors='coerce')
    
    # Sort by 'Time', with NaT values at the end
    combined_df = combined_df.sort_values('Time', ascending=False, na_position='last')
    
    # Define the columns to save, excluding 'ImageURL' if it doesn't exist
    columns_to_save = ['Title', 'Link', 'Description', 'Time']
    if 'ImageURL' in combined_df.columns:
        columns_to_save.append('ImageURL')
    
    combined_df.to_csv(filename, index=False, columns=columns_to_save)
    logging.info(f"Data saved to {filename}. Total items: {len(combined_df)}.")
    print(f"Data saved to {filename}. Total items: {len(combined_df)}.")

def scrape_nih_clinical_research_news():
    setup_logging()
    url = "https://www.nih.gov/health-information/nih-clinical-research-trials-you/news"
    output_file = "databases/nih_clinical_research.csv"
    
    logging.info(f"Starting scrape for {url}")

    html_content = fetch_webpage(url)
    if html_content:
        news_items = extract_nih_news_items(html_content)
        if news_items:
            save_to_csv(news_items, output_file)
        else:
            logging.info("No new items found.")
    else:
        logging.error("Failed to fetch webpage content.")

    logging.info("Scraping completed.")

if __name__ == "__main__":
    scrape_nih_clinical_research_news()
