import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import logging
from urllib.parse import urljoin, urlparse

def setup_logging(log_file):
    logging.basicConfig(filename=log_file, level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_webpage(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logging.error(f"Error fetching {url}: {e}")
        return None

def extract_links(html_content, base_url):
    soup = BeautifulSoup(html_content, 'html.parser')
    links = []
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        full_url = urljoin(base_url, href)
        links.append({
            'text': a_tag.text.strip(),
            'url': full_url,
            'is_internal': urlparse(full_url).netloc == urlparse(base_url).netloc
        })
    return links

def save_to_csv(data, filename):
    df = pd.DataFrame(data)
    df.to_csv(filename, index=False)
    logging.info(f"Data saved to {filename}")

def scrape_links(url, output_file):
    setup_logging('link_scraper.log')
    logging.info(f"Starting scrape for {url}")

    html_content = fetch_webpage(url)
    if html_content:
        links = extract_links(html_content, url)
        save_to_csv(links, output_file)
        logging.info(f"Scraping completed. Found {len(links)} links.")
    else:
        logging.error("Failed to fetch webpage content.")

# Example usage
if __name__ == "__main__":
    target_url = "https://example.com"
    output_csv = "scraped_links.csv"
    scrape_links(target_url, output_csv)
