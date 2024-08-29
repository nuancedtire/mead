import http.client
import json
import os
import pandas as pd
from datetime import datetime
import logging

# Set up logging
log_folder = 'logs'
log_file_path = os.path.join(log_folder, 'scape.log')
os.makedirs(log_folder, exist_ok=True)

logging.basicConfig(filename=log_file_path, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

logging.info('Script started.')

try:
    # Establish a connection
    conn = http.client.HTTPSConnection("www.medscape.co.uk")

    # Parameters for the request
    page = "1"
    limit = "30"

    # Headers for the request
    headers = {
        'priority': "u=1, i",
        'referer': "https://www.medscape.co.uk/",
        'sec-ch-ua': "\"Not)A;Brand\";v=\"99\", \"Brave\";v=\"127\", \"Chromium\";v=\"127\"",
        'sec-ch-ua-mobile': "?0",
        'sec-ch-ua-platform': "\"macOS\"",
        'sec-fetch-dest': "empty",
        'sec-fetch-mode': "cors",
        'sec-fetch-site': "same-origin",
        'sec-gpc': "1",
        'user-agent': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
    }
    
    # Make the GET request
    conn.request("GET", f"/api/rec-engine/api/v1/content_feed?aud=uk_web&page={page}&limit={limit}", headers=headers)

    # Get the response
    res = conn.getresponse()
    data = res.read()
    logging.info('Data fetched successfully from API.')

    # Decode the response into a Python dictionary
    data_dict = json.loads(data.decode("utf-8"))

    # Function to standardize time format
    def standardize_time(time_str):
        try:
            # Handle timestamps with timezone offsets
            dt = datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%S%z")
            # Convert to standard format 'YYYY-MM-DD HH:MM:SS' in UTC
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            logging.warning(f"Failed to standardize time format for {time_str}")
            return time_str  # Return the original string if parsing fails

    # Define the naming scheme similar to meds.csv with standardized time format
    filtered_data = [
        {
            "Title": item["field_engagement_title"],
            "Time": standardize_time(item["field_date_publish"]),
            "Link": item["field_canonical_url"],
            "Image URL": item["field_asset_thumbnail"],
            "Teaser": item["field_engagement_teaser"],
            "Source name": item["field_content_type"]
        }
        for item in data_dict.get("data", [])
        if item["field_content_type"] in ["Clinical Summary", "Guidelines in Practice"]  # Filter by content type
    ]

    # Convert to DataFrame
    df = pd.DataFrame(filtered_data)

    # Save to CSV (optional: change the filename/path as needed)
    csv_folder = 'databases'
    os.makedirs(csv_folder, exist_ok=True)
    csv_file_path = os.path.join(csv_folder, 'scape.csv')

    df.to_csv(csv_file_path, index=False)
    logging.info(f'Successfully saved data to {csv_file_path}.')

except Exception as e:
    logging.error(f"An error occurred: {e}")

logging.info('Scape script completed.')