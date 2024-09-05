import streamlit as st
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import re
import requests
import json
import time
from PIL import Image, ImageOps
from io import BytesIO
import datetime

# Define the fallback image URL
fallback_image_url = "https://peerr.io/images/logo.svg"  # Consider using a non-SVG format

# You can keep loading the additional CSV files as they are
meds = pd.read_csv('databases/meds.csv')
sifted = pd.read_csv('databases/sifted.csv')
scape = pd.read_csv('databases/scape.csv')

# Constants
api_key = 'AIzaSyAkJ8VVEHG7IAqwnUg9UuN8Hf_vttdMj2Y'
project_id = "peerr-cea41"
database_url = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/(default)/documents"
collection = "thoughts"
default_email = 'fazeennasser@gmail.com'
default_password = 'cowQiq-guzzas-buxse9'
# Fetch the firebase credentials from st.secrets
firebase_credentials = {
    "type": st.secrets["firebase"]["type"],
    "project_id": st.secrets["firebase"]["project_id"],
    "private_key_id": st.secrets["firebase"]["private_key_id"],
    "private_key": st.secrets["firebase"]["private_key"].replace("\\n", "\n"),  # Convert the newline characters
    "client_email": st.secrets["firebase"]["client_email"],
    "client_id": st.secrets["firebase"]["client_id"],
    "auth_uri": st.secrets["firebase"]["auth_uri"],
    "token_uri": st.secrets["firebase"]["token_uri"],
    "auth_provider_x509_cert_url": st.secrets["firebase"]["auth_provider_x509_cert_url"],
    "client_x509_cert_url": st.secrets["firebase"]["client_x509_cert_url"]
}
def load_firebase():
    # Check if the Firebase app is already initialized
    if not firebase_admin._apps:
        # Initialize the Firebase Admin SDK using the credentials file
        cred = credentials.Certificate(firebase_credentials)
        firebase_admin.initialize_app(cred)

    # Initialize Firestore client
    db = firestore.client()

    # Fetch data from Firestore collection "scraper-04-11-24"
    scraper_collection = db.collection('scraper-04-11-24')

    # Convert Firestore data to a Pandas DataFrame
    docs = scraper_collection.stream()
    data_list = []

    # Iterate over the generator to access document data
    for doc in docs:
        doc_dict = doc.to_dict()  # Convert Firestore document to dictionary
        data_list.append(doc_dict)

    # Create a DataFrame from the collected documents
    data = pd.DataFrame(data_list)

    # Convert the Timestamp to datetime
    data['Time'] = pd.to_datetime(data['Time'])
    data['Faz ID'] = data['LLM Timestamp']
    data['LLM Timestamp'] = pd.to_datetime(data['LLM Timestamp'])

    # Sort the data by Timestamp, latest at the top
    data = data.sort_values(by='Time', ascending=False)
    return data

def remove_markdown_formatting(text):
    # Replace bold (** or __) with uppercase
    text = re.sub(r'\*\*(.*?)\*\*', lambda m: m.group(1).upper(), text)
    text = re.sub(r'__(.*?)__', lambda m: m.group(1).upper(), text)
    
    # Remove italics (* or _)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'_(.*?)_', r'\1', text)
    
    # Removing headings
    text = re.sub(r'^\s*#+\s+', '', text, flags=re.MULTILINE)
    
    return text

def crop_to_fit(image_url, target_size=(640, 360)):
    """
    Downloads the image from the URL, resizes it while maintaining the aspect ratio, 
    and crops the excess parts to fit the target size.

    Args:
        image_url (str): The URL of the image to download and crop.
        target_size (tuple): The desired output size (width, height).
    
    Returns:
        Image: The resized and cropped image object.
    """
    try:
        # Download the image
        response = requests.get(image_url)
        if response.status_code == 200:
            img = Image.open(BytesIO(response.content))

            # Resize the image while maintaining aspect ratio, and center-crop to fit the target size
            img = ImageOps.fit(img, target_size, method=Image.LANCZOS)

            return img
        else:
            st.error(f"Failed to load image: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Error while downloading or processing the image: {str(e)}")
        return None

# Function to determine the source
def determine_source(link):
    if link in meds['Link'].values:
        return "Medsii"
    elif link in sifted['Link'].values:
        return "Sifted"
    elif link in scape['Link'].values:
        return "Medscape"
    else:
        return "Unknown Source"

# Function to clean and split hashtags properly
def clean_hashtags(hashtag_string):
    if pd.isna(hashtag_string):
        return []
    # Remove unwanted characters like brackets or extra spaces, then split by commas
    hashtags = hashtag_string.replace("[", "").replace("]", "").replace("'", "").split(',')
    # Strip any extra whitespace around the hashtags
    return [f"#{tag.strip()}" for tag in hashtags]

# Function to update Faz Firebase with Upload Status and Document ID
def update_upload_status(source_id, peerr_document_id, status):
    """
    Updates the upload status in the second Firestore database.

    Parameters:
        source_id (str): The ID of the document in the second Firestore database to update.
        status (bool): The upload status (True or False).

    Returns:
        bool: True if the status is successfully updated, False otherwise.
    """
    # Check if the Firebase app is already initialized
    if not firebase_admin._apps:
        # Initialize the Firebase Admin SDK using the credentials file
        cred = credentials.Certificate("firebase_creds.json")
        firebase_admin.initialize_app(cred)

    # Initialize Firestore client
    db = firestore.client()

    # Fetch data from Firestore collection "scraper-04-11-24"
    scraper_collection = db.collection('scraper-04-11-24')
    status_data = {
        "upload_status": status,
        "peerr_document_id": peerr_document_id,
    }

    try:
        # Update the document in the second Firestore database
        scraper_collection.document(source_id).set(status_data, merge=True)
        print(f"Upload status successfully updated to {status} for document {source_id} in the second Firestore database!")
        return True
    except Exception as e:
        print(f"Failed to update upload status for document {source_id} in the second Firestore database: {str(e)}")
        return False

def sign_in(email, password):
    """
    Authenticates the user with Firebase using email and password.

    Parameters:
        email (str): The user's email address.
        password (str): The user's password.

    Returns:
        tuple: A tuple containing the bearer token and the local ID of the user.

    Raises:
        Exception: If the sign-in fails, an exception is raised with the error message.
    """
    url = f'https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}'
    headers = {
        'accept': '*/*',
        'content-type': 'application/json',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36'
    }
    data = {
        "returnSecureToken": True,
        "email": email,
        "password": password
    }
    response = requests.post(url, headers=headers, data=json.dumps(data))
    if response.status_code == 200:
        tokens = response.json()
        return tokens.get('idToken'), tokens.get('localId')
    else:
        raise Exception(f"Failed to sign in: {response.status_code}, {response.text}")

def remove_markdown_formatting(text):
    """
    Removes markdown formatting from the provided text.

    Parameters:
        text (str): The input text with markdown formatting.

    Returns:
        str: The text with markdown formatting removed.
    """
    text = re.sub(r'\*\*(.*?)\*\*', lambda m: m.group(1).upper(), text)
    text = re.sub(r'__(.*?)__', lambda m: m.group(1).upper(), text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'_(.*?)_', r'\1', text)
    text = re.sub(r'^\s*#+\s+', '', text, flags=re.MULTILINE)
    return text

def post_to_firestore(source_id, post, image, email=None, password=None, localId=None, posted=None, updated=None, status="live"):
    email = email or default_email
    password = password or default_password
    
    bearer_token, user_local_id = sign_in(email, password)
    local_id = localId or user_local_id

    post = remove_markdown_formatting(post)
    postedTs = posted or int(time.time())
    updatedTs = updated or int(time.time())

    post_data = {
        "fields": {
            "body": {"stringValue": post},
            "imageUrl": {"stringValue": f"{image}?auto=compress&cs=tinysrgb&fit=crop&h=360&w=640"},
            "isPinned": {"booleanValue": False},
            "status": {"stringValue": status},
            "postedTs": {"integerValue": postedTs},
            "updatedTs": {"integerValue": updatedTs},
            "userName": {"stringValue": "Fazeen"},
            "userPhoto": {"nullValue": None},
            "userId": {"stringValue": local_id},
            "likes": {"arrayValue": {"values": []}},
            "audience": {"stringValue": "General"},
            "parentItem": {"mapValue": {"fields": {}}},
            "parentItemType": {"stringValue": ""},
            "priority": {"integerValue": 100}
        }
    }

    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json"
    }

    response = requests.post(f"{database_url}/{collection}", headers=headers, data=json.dumps(post_data))

    if response.status_code in [200, 201]:
        peerr_document_id = response.json()['name'].split('/')[-1]
        print("Post successfully added to Firestore!")
        
        # Update upload status in the second database
        update_upload_status(source_id, peerr_document_id, True)
        
        return peerr_document_id
    else:
        print("Failed to add post to Firestore!")
        return response.text

def delete_from_firestore(source_id, document_id, email=None, password=None):
    email = email or default_email
    password = password or default_password
    
    bearer_token, _ = sign_in(email, password)
    
    # Update upload status to False in the second database before deleting the document
    update_upload_status(source_id, document_id, False)
    
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json"
    }
    
    url = f"{database_url}/{collection}/{document_id}"
    response = requests.delete(url, headers=headers)

    if response.status_code == 200:
        print("Document successfully deleted from Firestore!")
        return True
    else:
        print("Failed to delete document from Firestore!")
        return response.text

# Function to create a post
def create_post(timestamp, llm_timestamp, hashtags, image_url, content, model, link, prompt, upload_status, peerr_document_id, source_id):
    if not image_url:
        image_url = fallback_image_url
    source = determine_source(link)
        
    # Create two columns for the thumbnail and the published time
    col1, col2 = st.columns([3, 5])
    
    with col1:
        # Crop the image to a specific size (left, upper, right, lower)
        cropped_image = crop_to_fit(image_url, target_size=(640, 360))
        if cropped_image:
            st.image(cropped_image)
            st.caption(f"Image courtesy [Pexels]({image_url})")
        else:
            st.error("Could not display the image.")
    
    with col2:
        st.info(f"**Published at:** {timestamp}  \n**Generated at:** {llm_timestamp}  \n**From:** {source}")
        if upload_status == True:
            st.write(f'🟢 Live on Peerr | ID: {peerr_document_id}')
            if st.button("Delete from Peerr", key=source_id):
                delete_from_firestore(source_id, peerr_document_id)
                update_upload_status(source_id, peerr_document_id, False)
                st.rerun()
        else:
            st.write(f'🔴 Not on Peerr')
            if st.button("Post to Peerr", key=source_id):
                new_peerr_document_id = post_to_firestore(source_id, content, image_url)  # Correct function for posting
                update_upload_status(source_id, new_peerr_document_id, True)
                st.rerun()
    # Extract the first line of the content
    if "\n" in content:
        first_line, rest_of_content = content.split('\n', 1)
    else:
        first_line = content[:40]
        rest_of_content = content

    tab1, tab2 = st.tabs(["Article", "Prompt"])
    
    with tab1:
        with st.expander(f"{first_line}"):
            st.write(rest_of_content)
    with tab2:
        st.header("Prompt")
        st.write(prompt)
    
    st.markdown("""
      <style>
      .stMarkdown hr {
      margin-top: -12px;
      margin-bottom: -6px;
      }
      </style>
      """, unsafe_allow_html=True)

    st.markdown("---")

# Streamlit UI
st.set_page_config(
   page_title="Peerr Thoughts",
   page_icon="💭",
   layout="wide",
)

st.title("Feed")
data = load_firebase()

with st.sidebar:

    # Statistics Section
    total_posts = len(data)
    last_post_time = data['Time'].max().strftime("%H:%M on %d-%m-%Y")
    first_post_time = data['Time'].min().strftime("%H:%M on %d-%m-%Y")
    last_gen_time = data['LLM Timestamp'].max().strftime("%H:%M on %d-%m-%Y")

    st.sidebar.success(f"**Total Posts:** *{total_posts}*  \n**Last Post:** *{last_post_time}*  \n**First Post:** *{first_post_time}*  \n**Last Gen:** *{last_gen_time}*")

# Sidebar description
st.sidebar.markdown("""Hello Team Peerr!

This app is a demo frontend for displaying a feed of posts as they get updated. 
The main section shows the latest posts, with each post displaying the publish time, 
an image (open source), and a snippet of the content.
You can expand each post to view the full content. You can also filter by date or tags below.
""")

# Hashtag Filter in Sidebar
st.sidebar.header("Filter by Hashtags")

# Apply the cleaning function to the Hashtags column
data['Hashtags'] = data['Hashtags'].apply(clean_hashtags)

# Extract unique hashtags
unique_hashtags = set(sum(data['Hashtags'].tolist(), []))

# Create a multi-select widget
selected_hashtags = st.sidebar.multiselect("Select Hashtags", options=list(unique_hashtags))

# Date Filter in Sidebar
st.sidebar.header("Filter by Date")
# start_date = st.sidebar.date_input("Start Date", value=data['Time'].min().date())
# Set the start date to 4th September 2024
start_date = st.sidebar.date_input("Start Date", value=datetime.date(2024, 9, 4))
end_date = st.sidebar.date_input("End Date", value=data['Time'].max().date())

# Filter data based on the selected date range
filtered_data = data[(data['Time'].dt.date >= start_date) & (data['Time'].dt.date <= end_date)]

# Filter data based on the selected hashtags
if selected_hashtags:
    filtered_data = filtered_data[filtered_data['Hashtags'].apply(lambda x: any(hashtag in x for hashtag in selected_hashtags))]

# Create a scrolling feed
if filtered_data.empty:
    st.write("No posts found for the selected date range and hashtags.")
else:
    for _, row in filtered_data.iterrows():
        create_post(
            timestamp=row['Time'].strftime("%H:%M on %d-%m-%Y"),
            llm_timestamp=row['LLM Timestamp'].strftime("%H:%M on %d-%m-%Y"),
            image_url=row['Image'],
            hashtags=row['Hashtags'],  # Pass raw hashtags here, processing happens inside create_post
            content=remove_markdown_formatting(row['Post']),
            model=row['Model'],
            link=row['Link'],
            prompt=row['Prompt'],
            upload_status=False if 'upload_status' not in row or pd.isna(row['upload_status']) else row['upload_status'],
            source_id=row['Faz ID'],
            peerr_document_id=None if 'peerr_document_id' not in row or pd.isna(row['peerr_document_id']) else row['peerr_document_id']
        )
