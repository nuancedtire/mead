import os
import logging
import requests
import pandas as pd
from datetime import datetime
import config
import re
from typing import List, Literal
from enum import Enum
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import (
    RunnableLambda,
    RunnableMap,
    RunnableParallel,
    RunnablePassthrough,
)
from langchain_openai import ChatOpenAI
from langchain_community.cache import SQLiteCache
from langchain_core.globals import set_llm_cache
from operator import itemgetter
from pydantic import BaseModel, Field, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from requests.exceptions import RequestException

# =====================
#  Logging Setup
# =====================

def setup_logger(log_file_path="logs/llm.log"):
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
    logging.basicConfig(
        filename=log_file_path,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

# =====================
#  Configuration Setup
# =====================

# Load OpenAI models and prompts from the config file
small_model_name = config.llm_config["small_model"]
large_model_name = config.llm_config["large_model"]
system_message = config.llm_config["system_prompt"]
hashtags = config.llm_config["hashtags"]
pexels_api_key = "zeaB9f5KanEeG8emVGlw9YlBQLCl0MbuG8KFqmOAfgaKispTcwMrBXqX"
os.environ['FAL_KEY'] = '74a025a1-190d-41e5-bd1a-c562f9b60293:3e6729b020fd14f6c6e409b7e08836a0'

# =====================
#  OpenAI API Setup and Caching
# =====================

# Initialize the LLMs
small_llm = ChatOpenAI(model=small_model_name, temperature=0.2)
large_llm = ChatOpenAI(model=large_model_name, temperature=0.2)

# Set up caching for LLM calls
set_llm_cache(SQLiteCache(database_path="langcache.db"))

# =====================
#  CSV File Handling
# =====================

def read_csv(file_path):
    if not os.path.exists(file_path):
        logging.warning(f"{file_path} does not exist, skipping...")
        print(f"{file_path} does not exist, skipping...")
        return pd.DataFrame()
    return pd.read_csv(file_path)

def extract_links(df, link_column="Link", time_column="Time"):
    try:
        if df.empty:
            logging.warning("The DataFrame is empty.")
            return []
        if link_column not in df.columns or time_column not in df.columns:
            logging.warning(f"Missing required columns: {link_column} or {time_column}")
            return []
        links = df.dropna(subset=[link_column])[[link_column, time_column]]
        link_records = links.to_dict("records")
        logging.info(f"Extracted {len(link_records)} link records.")
        return link_records
    except Exception as e:
        logging.error(f"Error extracting links: {str(e)}")
        return []

def extract_image_links(df, image_column="Image"):
    try:
        if df.empty:
            logging.warning("The DataFrame is empty.")
            return []
        if image_column not in df.columns:
            logging.warning(f"'{image_column}' column not found in the DataFrame.")
            return []
        image_links = df[image_column].dropna().tolist()
        logging.info(f"Extracted {len(image_links)} image links.")
        return image_links
    except Exception as e:
        logging.error(f"Error extracting image links: {str(e)}")
        return []

# =====================
#  Link Processing
# =====================

def remove_markdown_formatting(text):
    text = re.sub(r"\*\*(.*?)\*\*", lambda m: m.group(1).upper(), text)
    text = re.sub(r"__(.*?)__", lambda m: m.group(1).upper(), text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"_(.*?)_", r"\1", text)
    text = re.sub(r"^\s*#+\s+", "", text, flags=re.MULTILINE)
    return text

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(RequestException)
)
def fetch_url_content(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.text

# =====================
#  Pydantic Model for Response
# =====================

# Create an Enum for Hashtags
# HashtagEnum = Enum("HashtagEnum", {tag: tag for tag in hashtags})

class PostResponse(BaseModel):
    """Ready to use Social Media Post"""
    post_content: str = Field(..., description="The final generated post content in plain text without any hashtags.")
    hashtags: List[str] = Field(..., description="A list of relevant hashtags for the post.")
    category: Literal["Life Sciences & BioTech", "Research & Clinical Trials", "HealthTech & Startups", "Healthcare & Policy"] = Field(..., description="The category that fits the post best.")

# =====================
#  OpenAI API and Post Generation
# =====================

def generate_post(inputs):
    webpage_content = inputs["webpage_content"]
    link = inputs["link"]
    original_timestamp = inputs["original_timestamp"]
    processed_links = inputs["processed_links"]

    # Step 1: Check if the content is an article
    check_article_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Determine if the provided webpage contains a full article. "
                "If it does not contain an article, reply with only 'None'. "
                "If the webpage contains an article, convert the entire content into plain text, "
                "preserving the original text without summarization, additions, or omissions.",
            ),
            ("user", "{webpage_content}"),
        ]
    )
    check_article_chain = check_article_prompt | small_llm

    # Invoke the chain
    content_check_response = check_article_chain.invoke({"webpage_content": webpage_content})
    content_check = content_check_response.content.strip()

    if content_check.lower() == "none":
        logging.info(f"No article found for link {link}.")
        print(f"No article found for link {link}.")
        return None

    content = content_check
    if not content:
        logging.info(f"Empty content for link {link}.")
        print(f"Empty content for link {link}.")
        return None

    # Step 2: Generate the post using structured output
    structured_large_llm = large_llm.with_structured_output(PostResponse)
    post_generation_prompt = ChatPromptTemplate.from_messages(
        [("system", system_message), ("user", "Source: {link} \n{content}")]
    )
    post_generation_chain = post_generation_prompt | structured_large_llm

    try:
        post_response = post_generation_chain.invoke({"link": link, "content": content})
        parsed_response = post_response  # Already a PostResponse object
    except ValidationError as e:
        logging.error(f"Validation error for link {link}: {e}")
        print(f"Validation error for link {link}: {e}")
        return None

    # Step 3: Generate image query
    image_query = get_image_query(parsed_response.post_content, small_llm)
    logging.info(f"Image query: {image_query}")

    # Fetch image
    image_link = get_image(image_query)
    logging.info(f"Image link: {image_link}")

    # Combine category and hashtags
    combined_hashtags = [parsed_response.category] + parsed_response.hashtags
    # Append the processed information to processed_links
    processed_links.append({"Image": image_link})

    post_content = remove_markdown_formatting(parsed_response.post_content)

    # Return the log entry
    llm_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "status": "success",
        "generated_post": [
            original_timestamp,
            llm_timestamp,
            post_content,
            combined_hashtags,
            image_link,
            link,
            system_message,
            content,
            large_model_name,
        ],
        "link": link,
        "og_time": original_timestamp,
    }

def get_image_query(post_content, model):
    image_query_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """Task:

Analyze the following social media post related to medicine or healthcare and generate a vivid, detailed prompt for image generation that captures the post's core message and content.

Guidelines:

1. Focus on the Core Medical Topic and Setting:
   - Identify the main medical subject and setting described in the post.
2. Create a Vivid and Detailed Description:
   - Craft a captivating and imaginative description that includes visual details, emotions, and atmosphere.
   - Use descriptive language to paint a clear and engaging image.
3. Reflect the Post's Tone and Intent:
   - Align the prompt with the tone of the post—serious, educational, inspirational, etc.
4. Incorporate Artistic Elements:
   - Include stylistic elements or artistic styles if appropriate (e.g., "cinematic," "watercolor painting," "surreal").
5. Use Relevant Keywords:
   - Add keywords that enhance the prompt and guide image generation tools.
6. Maintain Appropriateness:
   - Ensure the prompt is respectful and avoids any disallowed or sensitive content.

Output:

- Provide the vivid, detailed prompt that effectively captures the essence of the social media post.
- Do not include any additional text or explanations.""",
            ),
            ("user", "{input}"),
        ]
    )
    image_query_chain = image_query_prompt | model
    image_query_response = image_query_chain.invoke({"input": post_content})
    return image_query_response.content.strip()

# Add Fal AI integration
import fal_client

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(RequestException)
)
def get_fal_ai_image(image_query):
    try:
        handler = fal_client.submit(
            "fal-ai/flux/schnell",
            arguments={
                "prompt": image_query
            },
        )
        result = handler.get()
        image_url = result['images'][0]['url']
        logging.info(f"Successfully generated image with Fal AI: {image_url}")
        return image_url
    except Exception as e:
        logging.error(f"Error generating image with Fal AI: {str(e)}")
        return ""

# Replace the get_unique_image function with this simplified version
def get_image(image_query):
    image_link = get_fal_ai_image(image_query)
    if not image_link:
        logging.warning(f"No image generated for query '{image_query}'. Quittin'.")
        return None
    return image_link

def normalize_url(url):
    if not url:
        return None
    return url.strip().rstrip("/").lower()

# =====================
#  Logging to CSV
# =====================

def log_to_csv_pandas(log_entry, document_id, file_name="databases/llm.csv"):
    try:
        generated_post = log_entry.get("generated_post")
        if not generated_post:
            logging.error("Cannot log to CSV: 'generated_post' is missing or empty.")
            return
        logging.info(f"'generated_post' length: {len(generated_post)}. Content: {generated_post}")
        columns = [
            "Time",
            "LLM Timestamp",
            "Post",
            "Hashtags",
            "Image",
            "Link",
            "Prompt",
            "Input",
            "Model",
            "DocumentID",
        ]
        log_entry_with_id = generated_post + [document_id]
        df_new = pd.DataFrame([log_entry_with_id], columns=columns)
        if not os.path.exists(file_name):
            df_new.to_csv(file_name, index=False)
        else:
            df_new.to_csv(file_name, mode="a", index=False, header=False)
        logging.info(f"Logged data to {file_name} with DocumentID: {document_id}.")
        print(f"Logged data to {file_name} with DocumentID: {document_id}.")
    except Exception as e:
        logging.error(f"Error logging data to CSV: {e}")
        print(f"Error logging data to CSV: {e}")

def send_to_firebase(batch_log_entries, url="https://flask-app-923186021986.us-central1.run.app/post"):
    # try:
    #     batch_data = []
    #     for log_entry in batch_log_entries:
    #         if not log_entry.get("generated_post"):
    #             logging.error("No 'generated_post' found in log entry or 'generated_post' is None.")
    #             continue
    #         audience = "HCP (inc. Students)" if "medscape" in log_entry["generated_post"][5] else "General"
    #         post_data = {
    #             "imageURL": log_entry["generated_post"][4],
    #             "hashtags": log_entry["generated_post"][3],
    #             "source": log_entry["generated_post"][5],
    #             "post": log_entry["generated_post"][2],
    #             "audience": audience,
    #         }
    #         batch_data.append(post_data)
    #     if not batch_data:
    #         logging.error("No valid log entries to send to Firebase.")
    #         return None
    #     headers = {"Content-Type": "application/json", "x-api-key": "fazzu"}
    #     response = requests.post(url, json={"posts": batch_data}, headers=headers)
    #     if response.status_code == 201:
    #         result = response.json()
    #         document_ids = result.get("documentIDs", [])
    #         logging.info(f"Successfully sent batch data to Firebase: {result}")
    #         if len(document_ids) != len(batch_log_entries):
    #             logging.error(
    #                 f"Mismatch in the number of document IDs and batch log entries. Got {len(document_ids)} document IDs for {len(batch_log_entries)} entries."
    #             )
    #             return None
    #         return document_ids
    #     else:
    #         logging.error(f"Failed to send batch data to Firebase. Status code: {response.status_code}, Response: {response.text}")
    #         return None
    # except requests.exceptions.RequestException as e:
    #     logging.error(f"Error sending batch data to Firebase: {e}")
    #     return None
    # Placeholder for Firebase sending
    logging.info(f"Placeholder: Would have sent {len(batch_log_entries)} entries to Firebase.")
    # Return placeholder document IDs
    return [f"placeholder_id_{i}" for i in range(len(batch_log_entries))]
# =====================
#  Main Logic
# =====================

def get_unique_links(csv_files, llm_links):
    combined_links = []
    for file in csv_files:
        df = read_csv(file)
        links = extract_links(df)
        combined_links += links
    return [
        link
        for link in combined_links
        if normalize_url(link["Link"]) not in llm_links
    ]

def main():
    setup_logger()
    csv_files = ["databases/meds.csv", "databases/sifted.csv", "databases/scape.csv"]
    llm_file_path = "databases/llm.csv"
    if os.path.exists(llm_file_path):
        llm_links = [normalize_url(entry["Link"]) for entry in extract_links(read_csv(llm_file_path))]
    else:
        llm_links = []
    combined_links = get_unique_links(csv_files, llm_links)
    logging.info(f"Unique links to process: {len(combined_links)}")
    print(f"Unique links to process: {len(combined_links)}")
    if not combined_links:
        logging.info("No unique links to process.")
        print("No unique links to process.")
        return

    # Prepare inputs for processing
    batch_log_entries = []
    for link_info in combined_links:
        link = link_info.get("Link")
        if link is None:
            logging.warning(f"Invalid link found in link_info: {link_info}")
            continue
        url = f"http://r.jina.ai/{link}"
        try:
            webpage_content = fetch_url_content(url)
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching {url}: {e}")
            continue
        inputs = {
            "webpage_content": webpage_content,
            "link": link,
            "original_timestamp": link_info.get("Time"),
            "processed_links": [],
        }
        log_entry = generate_post(inputs)
        if log_entry and log_entry.get("status") == "success":
            batch_log_entries.append(log_entry)
        else:
            logging.warning(f"Skipping entry due to missing or invalid log entry for link: {link}")

    if batch_log_entries:
        logging.info(f"Sending {len(batch_log_entries)} log entries to Firebase.")
        document_ids = send_to_firebase(batch_log_entries)
        if document_ids:
            logging.info(f"Received {len(document_ids)} document IDs from Firebase.")
            for log_entry, document_id in zip(batch_log_entries, document_ids):
                log_to_csv_pandas(log_entry, document_id)
        else:
            logging.warning("No document IDs returned from Firebase. Skipping CSV logging.")
    else:
        logging.info("No valid log entries generated.")

if __name__ == "__main__":
    main()
