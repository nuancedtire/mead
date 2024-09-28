import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import logging
import requests
import pandas as pd
from datetime import datetime, timedelta
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
import json

# =====================
#  Logging Setup
# =====================

def setup_logger(log_file_path="logs/llm.log"):
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    # Create a custom logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Create handlers
    f_handler = logging.FileHandler(log_file_path)
    f_handler.setLevel(logging.INFO)
    c_handler = logging.StreamHandler(sys.stdout)
    c_handler.setLevel(logging.INFO)

    # Create formatters and add them to the handlers
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    f_handler.setFormatter(formatter)
    c_handler.setFormatter(formatter)

    # Add handlers to the logger
    logger.addHandler(f_handler)
    logger.addHandler(c_handler)

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
        return pd.DataFrame()
    return pd.read_csv(file_path)

def extract_links(df, link_column="Link", time_column="Time", source_link_column="Source Link"):
    try:
        if df.empty:
            logging.warning("The DataFrame is empty.")
            return []
        if link_column not in df.columns or time_column not in df.columns:
            logging.warning(f"Missing required columns: {link_column} or {time_column}")
            return []
        
        # Check if source_link_column exists, if not, use link_column
        columns_to_extract = [link_column, time_column]
        if source_link_column in df.columns:
            columns_to_extract.append(source_link_column)
        else:
            logging.warning(f"'{source_link_column}' not found. Using '{link_column}' as source link.")
        
        links = df.dropna(subset=[link_column])[columns_to_extract]
        
        # If source_link_column doesn't exist, create it with the same value as link_column
        if source_link_column not in links.columns:
            links[source_link_column] = links[link_column]
        
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
    hashtags: List[str] = Field(..., description="A list of trending hashtags for the post. For example, Cardiology, HealthcarePolicy")
    category: Literal["Life Sciences & BioTech", "Research & Clinical Trials", "HealthTech & Startups", "Healthcare & Policy"] = Field(..., description="The category that fits the post best.")

# =====================
#  OpenAI API and Post Generation
# =====================

# Add this at the top of the file, after imports
FAILED_LINKS_FILE = "failed_links.json"

def load_failed_links():
    try:
        with open(FAILED_LINKS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_failed_links(failed_links):
    with open(FAILED_LINKS_FILE, 'w') as f:
        json.dump(failed_links, f)

def generate_post(inputs):
    try:
        webpage_content = inputs["webpage_content"]
        link = inputs["link"]
        source_link = inputs["source_link"]
        original_timestamp = inputs["original_timestamp"]
        processed_links = inputs["processed_links"]

        failed_links = load_failed_links()
        current_time = datetime.now()

        # Check if the link has failed recently
        if link in failed_links:
            last_failed_time = datetime.fromisoformat(failed_links[link])
            if current_time - last_failed_time < timedelta(hours=1):  # Adjust the time as needed
                logging.info(f"Skipping recently failed link: {link}")
                return None

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
            failed_links[link] = current_time.isoformat()
            save_failed_links(failed_links)
            return None

        content = content_check
        if not content:
            logging.info(f"Empty content for link {link}.")
            failed_links[link] = current_time.isoformat()
            save_failed_links(failed_links)
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
                source_link,  # Add source_link to the generated_post list
                system_message,
                content,
                large_model_name,
            ],
            "link": link,
            "source_link": source_link,  # Add source_link to the return dictionary
            "og_time": original_timestamp,
        }
    except Exception as e:
        logging.error(f"Error generating post for link {link}: {e}")
        return None

def get_image_query(post_content, model):
    image_query_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """**Task:**

Analyze the following social media post related to medicine or healthcare and generate a vivid, detailed image prompt that captures the essence of the post. The image prompt should guide AI image generation models to create compelling, **photorealistic**, and visually striking images that effectively communicate the core message of the post.

**Guidelines:**

1. **Identify the Core Medical Topic and Context:**
   - Determine the main subject and its significance (e.g., clinical trial results, healthcare policy updates).
   - Use precise and relevant medical terminology reflecting the central message.

2. **Be Specific and Descriptive:**
   - Provide detailed descriptions of key elements, including people, medical equipment, settings, and symbolic representations.
   - Focus on creating a coherent and impactful image without relying on text.

3. **Specify Photorealistic Style:**
   - Emphasize a photorealistic visual aesthetic for maximum realism and impact.
   - Avoid illustrative or overly stylized representations.

4. **Consider Composition and Perspective:**
   - Arrange elements to highlight the main message using focal points and dynamic angles.
   - Use perspectives that enhance engagement, such as close-ups or wide-angle shots.

5. **Utilize Lighting and Color Palette:**
   - Indicate lighting that complements the mood (e.g., bright lighting for positive news, subdued tones for serious updates).
   - Choose a color palette that aligns with medical and technological themes.

6. **Convey Mood and Emphasis:**
   - Reflect the emotional tone of the news (e.g., hopeful, urgent).
   - Use visual cues to convey importance and urgency.

7. **Maintain Appropriateness, Sensitivity, and Ethical Standards:**
   - Ensure the image is respectful and avoids disallowed or sensitive content.
   - Avoid graphic depictions, distressing imagery, and any personal or identifiable patient information.
   - Do not include text in the image.

8. **Enhance with Sensory and Emotional Details:**
   - Incorporate descriptions of textures, ambient sounds (as visual elements), or emotions to add depth to the image.

**Example Social Media Post:**

🧠 Navigating the complexities of aspirin therapy—how individualized approaches can prevent brain bleeds.

A recent study from the UK Biobank involving over 449,000 participants sheds light on the risks associated with regular aspirin use:

- Overall, aspirin does not significantly increase the risk of intracerebral hemorrhage (ICH) in middle-aged and older adults without a history of stroke or transient ischemic attack.
- Only 0.3% of participants experienced ICH during a median follow-up of 12.75 years, with a quarter being fatal.
- However, the risk escalates for:
  - Individuals over 65 years (hazard ratio of 1.47)
  - Those using anticoagulants concurrently (hazard ratio of 4.37)

These findings underscore the importance of individualized assessment when prescribing aspirin, particularly for older adults and those on anticoagulants. 

How do you approach aspirin therapy in your practice to balance benefits and risks?
**Example Prompt:**
A photorealistic image set in a contemporary medical consultation room. A middle-aged doctor in a crisp white coat sits across from an elderly male patient, around 70 years old, who is seated in a comfortable chair. The doctor leans forward slightly, hands resting calmly on his knees or clasped together, as he listens attentively to the patient. The patient’s expression is attentive yet slightly concerned, indicating they are discussing important health matters. A stethoscope hangs around the doctor’s neck, and a blood pressure monitor is placed on a nearby table, symbolizing recent medical examination. The room is well-lit with natural light filtering through the window, casting soft shadows that create a warm yet serious atmosphere. On the wall behind them, a framed poster illustrates the human brain, subtly emphasizing the topic of brain health and the risks associated with aspirin therapy and intracerebral hemorrhage. The composition captures a medium close-up angle, focusing on the empathetic interaction between the doctor and patient, highlighting the importance of personalized medical assessments in aspirin therapy for older adults. The overall mood conveys a sense of care and urgency, reflecting the critical nature of balancing benefits and risks in medication management.""",
            ),
            ("user", """Please generate the image prompt accordingly. Reply with only the prompt, no intro, no explanation, no nothing.

Social Media Post
---
{input}"""),
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
                "prompt": image_query,
                "image_size": "landscape_4_3",
                "num_inference_steps": 8,
                "num_images": 1,
                "enable_safety_checker": True
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
        logging.info(f"'generated_post' length: {len(generated_post)}")
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
        # Remove the source_link from generated_post
        log_entry_with_id = generated_post[:6] + generated_post[7:] + [document_id]
        df_new = pd.DataFrame([log_entry_with_id], columns=columns)
        if not os.path.exists(file_name):
            df_new.to_csv(file_name, index=False)
        else:
            df_new.to_csv(file_name, mode="a", index=False, header=False)
        logging.info(f"Logged data to {file_name} with DocumentID: {document_id}.")
    except Exception as e:
        logging.error(f"Error logging data to CSV: {e}")

# def send_to_firebase(batch_log_entries, url="https://peerr-website-git-api-thoughts-peerr.vercel.app/api/thoughts/add"):
#     try:
#         batch_data = []
#         for log_entry in batch_log_entries[:10]:  # Only take up to 10 posts
#             if not log_entry.get("generated_post"):
#                 logging.error("No 'generated_post' found in log entry or 'generated_post' is None.")
#                 continue
#             link = log_entry["generated_post"][5]
#             source_link = log_entry["generated_post"][6]  # Get the source_link
#             audience = "HCP (inc. Students)" if "medscape" in link or "nice" in link or "nih" in link else "General"
#             post_data = {
#                 "imageURL": log_entry["generated_post"][4],
#                 "hashtags": log_entry["generated_post"][3],
#                 "source": source_link if source_link else link,  # Use source_link if available, otherwise use link
#                 "post": log_entry["generated_post"][2],
#                 "type": audience,
#             }
#             batch_data.append(post_data)
#         if not batch_data:
#             logging.error("No valid log entries to send to API.")
#             return None
#         headers = {"Content-Type": "application/json", "x-secret": "9b7ExA8PlJbK"}
#         response = requests.post(url, json=batch_data, headers=headers)
#         if response.status_code == 201 or response.status_code == 200:
#             result = response.json()
#             document_ids = [item["message"].split(": ")[1] for item in result if "Saved with ID" in item["message"]]
#             logging.info(f"Successfully sent batch data to API: {result}")
#             if len(document_ids) != len(batch_log_entries[:10]):
#                 logging.error(
#                     f"Mismatch in the number of document IDs and batch log entries. Got {len(document_ids)} document IDs for {len(batch_log_entries[:10])} entries."
#                 )
#                 return None
#             return document_ids
#         else:
#             logging.error(f"Failed to send batch data to API. Status code: {response.status_code}, Response: {response.text}")
#             return None
#     except requests.exceptions.RequestException as e:
#         logging.error(f"Error sending batch data to API: {e}")
#         return None

def send_to_firebase(batch_log_entries, url="https://peerr-website-git-api-thoughts-peerr.vercel.app/api/thoughts/add"):
    try:
        batch_data = []
        for log_entry in batch_log_entries[:10]:  # Only take up to 10 posts
            if not log_entry.get("generated_post"):
                logging.error("No 'generated_post' found in log entry or 'generated_post' is None.")
                continue
            link = log_entry["generated_post"][5]
            source_link = log_entry["generated_post"][6]  # Get the source_link
            audience = "HCP (inc. Students)" if "medscape" in link or "nice" in link or "nih" in link else "General"
            post_data = {
                "imageURL": log_entry["generated_post"][4],
                "hashtags": log_entry["generated_post"][3],
                "source": source_link if source_link else link,  # Use source_link if available, otherwise use link
                "post": log_entry["generated_post"][2],
                "type": audience,
            }
            batch_data.append(post_data)
        if not batch_data:
            logging.error("No valid log entries to send to API.")
            return None
        
        # Generate placeholder IDs
        document_ids = [f"placeholder_id_{i}" for i in range(len(batch_data))]
        logging.info(f"Generated placeholder IDs: {document_ids}")
        
        return document_ids
    except Exception as e:
        logging.error(f"Error in send_to_firebase: {e}")
        return None
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
    csv_files = [
        "databases/meds.csv",
        "databases/sifted.csv",
        "databases/scape.csv",
        "databases/nice.csv",
        "databases/nih_clinical_research.csv",
        "databases/digital_health_news.csv" ,
        "databases/uktech_news.csv" # Added this line
    ]
    llm_file_path = "databases/llm.csv"
    
    # Load existing LLM links
    if os.path.exists(llm_file_path):
        llm_links = [normalize_url(entry["Link"]) for entry in extract_links(read_csv(llm_file_path))]
    else:
        llm_links = []
    
    # Get unique links to process
    combined_links = get_unique_links(csv_files, llm_links)
    logging.info(f"Unique links to process: {len(combined_links)}")
    if not combined_links:
        logging.info("No unique links to process.")
        return

    # Load failed links
    failed_links = load_failed_links()
    current_time = datetime.now()

    # Prepare inputs for processing
    batch_log_entries = []
    processed_count = 0
    for link_info in combined_links:
        if processed_count >= 5:  # Process only 5 articles
            break

        link = link_info.get("Link")
        source_link = link_info.get("Source Link", "")  # Get the Source Link, default to empty string if not present
        if link is None:
            logging.warning(f"Invalid link found in link_info: {link_info}")
            continue

        # Check if the link has failed recently
        if link in failed_links:
            last_failed_time = datetime.fromisoformat(failed_links[link])
            if current_time - last_failed_time < timedelta(hours=4):  # Adjust the time as needed
                logging.info(f"Skipping recently failed link: {link}")
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
            "source_link": source_link,  # Add source_link to the inputs
            "original_timestamp": link_info.get("Time"),
            "processed_links": [],
        }
        log_entry = generate_post(inputs)
        if log_entry and log_entry.get("status") == "success":
            batch_log_entries.append(log_entry)
            processed_count += 1
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
