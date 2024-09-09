# Import necessary libraries
import streamlit as st
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
import re
import requests
import json
import time
from PIL import Image, ImageOps
from io import BytesIO
import datetime
from dateutil.relativedelta import relativedelta

def convert_to_datetime(dt):
    """Converts a string or other formats to a datetime object if necessary."""
    if isinstance(dt, str):
        try:
            # Assuming the string is in the format '09:00 on 09-09-2024'
            return datetime.datetime.strptime(dt, '%H:%M on %d-%m-%Y')
        except ValueError:
            # Handle different or unexpected formats here
            raise ValueError(f"Timestamp format is incorrect: {dt}")
    elif isinstance(dt, datetime.datetime):
        return dt
    else:
        raise TypeError("Timestamp should be either a string or datetime object")

def relative_time(past_time):
    """Returns a human-readable relative time string like '2 hours ago'."""
    now = datetime.datetime.now()
    past_time = convert_to_datetime(past_time)  # Ensure it's a datetime object
    diff = relativedelta(now, past_time)

    if diff.years > 0:
        return f"{diff.years} years ago"
    elif diff.months > 0:
        return f"{diff.months} months ago"
    elif diff.days > 0:
        return f"{diff.days} days ago"
    elif diff.hours > 0:
        return f"{diff.hours} hours ago"
    elif diff.minutes > 0:
        return f"{diff.minutes} minutes ago"
    else:
        return "just now"

# Fallback image in case the provided image URL is invalid or missing
fallback_image_url = "https://peerr.io/images/logo.svg"  # Note: SVG might not be ideal for image display. Consider using a PNG or JPEG.

# Load CSV files containing data sources
meds = pd.read_csv('databases/meds.csv')   # Medsii data
sifted = pd.read_csv('databases/sifted.csv')  # Sifted data
scape = pd.read_csv('databases/scape.csv')  # Medscape data

# Firebase and API configurations
api_key = 'AIzaSyAkJ8VVEHG7IAqwnUg9UuN8Hf_vttdMj2Y'  # Consider hiding this in st.secrets
project_id = "peerr-cea41"
database_url = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/(default)/documents"
collection = "thoughts"
default_email = 'fazeennasser@gmail.com'  # Store sensitive data like this in `st.secrets` for security
default_password = 'cowQiq-guzzas-buxse9'

# Load Firebase credentials from Streamlit secrets
firebase_credentials = {
    "type": st.secrets["firebase"]["type"],
    "project_id": st.secrets["firebase"]["project_id"],
    "private_key_id": st.secrets["firebase"]["private_key_id"],
    "private_key": st.secrets["firebase"]["private_key"].replace("\\n", "\n"),  # Convert escaped newline characters to actual newlines
    "client_email": st.secrets["firebase"]["client_email"],
    "client_id": st.secrets["firebase"]["client_id"],
    "auth_uri": st.secrets["firebase"]["auth_uri"],
    "token_uri": st.secrets["firebase"]["token_uri"],
    "auth_provider_x509_cert_url": st.secrets["firebase"]["auth_provider_x509_cert_url"],
    "client_x509_cert_url": st.secrets["firebase"]["client_x509_cert_url"]
}

# Centralized Firebase Initialization Function
def initialize_firebase():
    """
    Initialize the Firebase Admin SDK if it's not already initialized.
    This function is used to avoid redundant Firebase initialization checks.
    """
    if not firebase_admin._apps:
        cred = credentials.Certificate(firebase_credentials)
        firebase_admin.initialize_app(cred)

# Modified Firebase Initialization in Functions
def load_firebase():
    """
    Load data from Firestore and return it as a Pandas DataFrame.
    """
    initialize_firebase()  # Call centralized Firebase initialization
    db = firestore.client()
    scraper_collection = db.collection('scraper-09-11-24')
    docs = scraper_collection.stream()
    data_list = [doc.to_dict() for doc in docs]
    
    # Convert to DataFrame and process timestamps
    data = pd.DataFrame(data_list)
    data['Time'] = pd.to_datetime(data['Time'])
    data['LLM_Timestamp'] = pd.to_datetime(data['LLM_Timestamp'])
    data = data.sort_values(by='Time', ascending=False)
    return data

# Function to remove markdown formatting from text
def remove_markdown_formatting(text):
    # Convert bold text (**) to uppercase
    text = re.sub(r'\*\*(.*?)\*\*', lambda m: m.group(1).upper(), text)
    text = re.sub(r'__(.*?)__', lambda m: m.group(1).upper(), text)
    
    # Remove italics formatting
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'_(.*?)_', r'\1', text)
    
    # Remove markdown headings (#)
    text = re.sub(r'^\s*#+\s+', '', text, flags=re.MULTILINE)
    
    return text

# Function to download, resize, and crop an image to fit the target size
def crop_to_fit(image_url, target_size=(640, 360)):
    """
    Download the image from the URL, resize and crop to fit the specified size.

    Args:
        image_url (str): The URL of the image.
        target_size (tuple): Desired image size in (width, height).

    Returns:
        Image: Cropped and resized image object, or None in case of an error.
    """
    try:
        response = requests.get(image_url)
        if response.status_code == 200:
            img = Image.open(BytesIO(response.content))

            # Resize while maintaining aspect ratio and crop to fit target size
            img = ImageOps.fit(img, target_size, method=Image.LANCZOS)
            return img
        else:
            st.error(f"Failed to load image: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Error while processing the image: {str(e)}")
        return None

# Function to identify the source of a post based on the link
def determine_source(link):
    """
    Identifies the source of the article based on the provided link.
    
    Args:
        link (str): The URL link of the article.
    
    Returns:
        str: Source of the article.
    """
    if link in meds['Link'].values:
        return "Medsii"
    elif link in sifted['Link'].values:
        return "Sifted"
    elif link in scape['Link'].values:
        return "Medscape"
    else:
        return "Unknown Source"

# Improved Hashtag Cleaning Function to Handle Array Inputs
def clean_hashtags(hashtag_string):
    """
    Clean and format hashtags, handling cases where hashtags might already be an array.
    
    Args:
        hashtag_string (str or list): A string or list of hashtags.
    
    Returns:
        list: A list of cleaned hashtags, properly formatted with #.
    """
    if isinstance(hashtag_string, list):  # If it's already an array, return it directly
        return [f"#{tag.strip()}" for tag in hashtag_string]
    
    if pd.isna(hashtag_string):  # Handle NaN cases
        return []

    # If it's a string, remove unwanted characters and split by commas
    hashtags = hashtag_string.replace("[", "").replace("]", "").replace("'", "").split(',')
    return [f"#{tag.strip()}" for tag in hashtags]

# Update upload status for a document in Firestore
def update_upload_status(source_id, peerr_document_id, status):
    """
    Updates the upload status of a document in Firestore.

    Args:
        source_id (str): The ID of the document in Firestore.
        peerr_document_id (str): Document ID in Firestore.
        status (bool): Upload status (True or False).

    Returns:
        bool: True if successfully updated, False otherwise.
    """
    try:
        initialize_firebase()  # Centralized Firebase initialization
        db = firestore.client()
        scraper_collection = db.collection('scraper-09-11-24')
        status_data = {
            "upload_status": status,
            "peerr_document_id": peerr_document_id,
        }
        scraper_collection.document(source_id).set(status_data, merge=True)
        st.success(f"Upload status successfully updated for document {source_id}.")
        return True
    except Exception as e:
        st.error(f"Failed to update status for document {source_id}: {str(e)}")
        return False

# Function to sign in to Firebase
def sign_in(email, password):
    """
    Sign in a user to Firebase using email and password.

    Args:
        email (str): The user's email.
        password (str): The user's password.

    Returns:
        tuple: Bearer token and local user ID from Firebase.
    """
    url = f'https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}'
    data = {
        "returnSecureToken": True,
        "email": email,
        "password": password
    }
    response = requests.post(url, data=json.dumps(data))
    
    if response.status_code == 200:
        tokens = response.json()
        return tokens.get('idToken'), tokens.get('localId')
    else:
        raise Exception(f"Failed to sign in: {response.status_code}, {response.text}")

# Function to post content to Firestore
def post_to_firestore(source_id, post, image, email=None, password=None, localId=None, posted=None, updated=None, status="live"):
    """
    Upload a new post to Firestore with the given content and metadata.

    Args:
        source_id (str): ID of the source document.
        post (str): The content of the post.
        image (str): Image URL for the post.
        email (str): User email for Firebase authentication.
        password (str): User password for Firebase authentication.
        localId (str): User's local ID in Firebase.
        posted (int): Timestamp of when the post was created.
        updated (int): Timestamp of when the post was last updated.
        status (str): Post status (e.g., "live").

    Returns:
        str: Document ID of the newly created post in Firestore, or an error message.
    """
    email = email or default_email
    password = password or default_password

    # Authenticate user
    bearer_token, user_local_id = sign_in(email, password)
    local_id = localId or user_local_id

    # Clean and format post content
    post = remove_markdown_formatting(post)
    postedTs = posted or int(time.time())
    updatedTs = updated or int(time.time())

    # Prepare post data for Firestore
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
            "priority": {"integerValue": 100}
        }
    }

    # Send the post request to Firestore
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json"
    }

    response = requests.post(f"{database_url}/{collection}", headers=headers, data=json.dumps(post_data))

    if response.status_code in [200, 201]:
        peerr_document_id = response.json()['name'].split('/')[-1]
        print("Post successfully added to Firestore!")
        
        # Update upload status in the second Firestore collection
        update_upload_status(source_id, peerr_document_id, True)
        
        return peerr_document_id
    else:
        print("Failed to add post to Firestore!")
        return response.text

# Function to delete a post from Firestore
def delete_from_firestore(source_id, document_id, email=None, password=None):
    """
    Delete a post from Firestore and update its upload status.

    Args:
        source_id (str): ID of the source document.
        document_id (str): Document ID to be deleted from Firestore.
        email (str): User email for Firebase authentication.
        password (str): User password for Firebase authentication.

    Returns:
        bool: True if deletion was successful, False otherwise.
    """
    email = email or default_email
    password = password or default_password
    
    # Authenticate user
    bearer_token, _ = sign_in(email, password)
    
    # Update upload status to False before deletion
    update_upload_status(source_id, document_id, False)
    
    # Send delete request to Firestore
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

# Function to create a post in the UI
def create_post(timestamp, llm_timestamp, hashtags, image_url, content, model, link, prompt, upload_status, peerr_document_id, source_id, input):
    """
    Renders a single post in the Streamlit feed with associated metadata and content.

    Args:
        timestamp (str): Time when the post was published.
        llm_timestamp (str): Time when the post was generated by the LLM.
        hashtags (list): List of hashtags associated with the post.
        image_url (str): URL of the image to display with the post.
        content (str): Main content of the post.
        model (str): Model used to generate the post.
        link (str): Link to the original article.
        prompt (str): Input prompt used for generating the post.
        upload_status (bool): Upload status to indicate if the post is live.
        peerr_document_id (str): Document ID in Firestore (if already uploaded).
        source_id (str): ID of the source document.
        input (str): Original input text for the post generation.
    """
    # Use fallback image if no image URL is provided
    if not image_url:
        image_url = fallback_image_url
    source = determine_source(link)
    
    # Create two columns: one for the image and one for post metadata
    col1, col2 = st.columns([3, 5])
    
    with col1:
        # Display the image after cropping to the desired size
        cropped_image = crop_to_fit(image_url, target_size=(640, 360))
        if cropped_image:
            st.image(cropped_image)
            st.caption(f"Image courtesy [Pexels]({image_url})")
        else:
            st.error("Could not display the image.")
    with col2:
        # st.info(f"**Published at:** {timestamp}  \n**Generated at:** {llm_timestamp}  \n**From:** {source}")
        # if upload_status == True:
        #     st.write(f'🟢 Live on Peerr | ID: {peerr_document_id}')
        #     if st.button("Delete from Peerr", key=source_id):
        #         delete_from_firestore(source_id, peerr_document_id)
        #         update_upload_status(source_id, peerr_document_id, False)
        #         st.rerun()  # Refresh the page after deletion
        # else:
        #     st.write(f'🔴 Not on Peerr')
        #     if st.button("Post to Peerr", key=source_id):
        #         new_peerr_document_id = post_to_firestore(source_id, content, image_url)
        #         update_upload_status(source_id, new_peerr_document_id, True)
        #         st.rerun()  # Refresh the page after posting
    
        # Create tabs for article content and more details
        first_line = content.split("\n")[0] if "\n" in content else content[:40]
        # Extract rest of the content, skipping the first line
        rest_of_content = "\n".join(content.split("\n")[1:]) 
        cleaned_content = re.sub(r"#\w+", "", rest_of_content)
        hashtags_str = " ".join(hashtags)

        tab1, tab2 = st.tabs(["Article", "More"])
        
        with tab1:
            with st.expander(f"{first_line}"):
                st.write(cleaned_content)
                st.write(f"**Generated Hashtags:** {hashtags_str}")
            # Display the relative times
            st.info(f"**Published** {relative_time(timestamp)}  \n"
                    # f"**Generated at:** {relative_time(llm_timestamp)}  \n"
                    f"**From:** {source}")   
        with tab2:
            st.write(content)
            st.write(hashtags)
            st.write(link)
            st.write(f"Input:  \n{remove_markdown_formatting(input)}")
        
    # Add a horizontal line between posts
    st.markdown("---")

# Streamlit UI configuration
st.set_page_config(
   page_title="Peerr Thoughts",
   page_icon="💭",
   layout="wide",
)

st.title("Feed")
data = load_firebase()

# Sidebar with various filters and statistics
with st.sidebar:

    # Display statistics
    total_posts = len(data)
    last_post_time = data['Time'].max().strftime("%H:%M on %d-%m-%Y")
    first_post_time = data['Time'].min().strftime("%H:%M on %d-%m-%Y")
    last_gen_time = data['LLM_Timestamp'].max().strftime("%H:%M on %d-%m-%Y")

    st.sidebar.success(f"**Total Posts:** *{total_posts}*  \n**Last Post:** *{last_post_time}*  \n**First Post:** *{first_post_time}*  \n**Last Gen:** *{last_gen_time}*")

# Sidebar description
st.sidebar.markdown("""Hello Team Peerr!

This app is a demo frontend for displaying a feed of posts as they get updated. 
The main section shows the latest posts, with each post displaying the publish time, 
an image (open source), and a snippet of the content.
You can expand each post to view the full content. You can also filter by date or tags below.
""")

# Hashtag filter in the sidebar
st.sidebar.header("Filter by Hashtags")

# Apply cleaning function to 'Hashtags' column
data['Hashtags'] = data['Hashtags'].apply(clean_hashtags)

# Extract unique hashtags and create a multi-select widget
unique_hashtags = set(sum(data['Hashtags'].tolist(), []))
selected_hashtags = st.sidebar.multiselect("Select Hashtags", options=list(unique_hashtags))

# Handle dynamic start date
st.sidebar.header("Filter by Date")
start_date = st.sidebar.date_input("Start Date", value=data['Time'].min().date())  # Dynamic start date from data
end_date = st.sidebar.date_input("End Date", value=data['Time'].max().date())

# Filter data by date range and selected hashtags
filtered_data = data[(data['Time'].dt.date >= start_date) & (data['Time'].dt.date <= end_date)]

if selected_hashtags:
    filtered_data = filtered_data[filtered_data['Hashtags'].apply(lambda x: any(hashtag in x for hashtag in selected_hashtags))]

# Display posts in a scrolling feed
if filtered_data.empty:
    st.write("No posts found for the selected date range and hashtags.")
else:
    for _, row in filtered_data.iterrows():
        create_post(
            timestamp=row['Time'].strftime("%H:%M on %d-%m-%Y"),
            llm_timestamp=row['LLM_Timestamp'].strftime("%H:%M on %d-%m-%Y"),
            image_url=row['Image'],
            hashtags=row['Hashtags'],
            content=remove_markdown_formatting(row['Post']),
            model=row['Model'],
            link=row['Link'],
            prompt=row['Prompt'],
            upload_status=False if 'upload_status' not in row or pd.isna(row['upload_status']) else row['upload_status'],
            source_id=row['Encoded_Link'],
            peerr_document_id=None if 'peerr_document_id' not in row or pd.isna(row['peerr_document_id']) else row['peerr_document_id'],
            input=row['Input']
        )
