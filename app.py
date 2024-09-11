# Import necessary libraries
import streamlit as st
import pandas as pd
import re
import requests
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

# Modified Firebase Initialization in Functions
def load_firebase():
    """
    Load data from LLM csv and return it as a Pandas DataFrame.
    """
    # Convert to DataFrame and process timestamps
    data = pd.read_csv('databases/llm.csv')
    data['Time'] = pd.to_datetime(data['Time'])
    data['LLM Timestamp'] = pd.to_datetime(data['LLM Timestamp'])
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

# Function to create a post in the UI
def create_post(timestamp, llm_timestamp, hashtags, image_url, content, model, link, prompt, input):
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
        st.info(f"{str(hashtags[0])[1:]}")
        st.write(f"**Published** {relative_time(timestamp)}  \n"
                # f"**Generated at:** {relative_time(llm_timestamp)}  \n"
                f"**From:** {source}  \n")
    with col2:
        first_line = content.split("\n")[0] if "\n" in content else content[:40]
        # Extract rest of the content, skipping the first line
        rest_of_content = "\n".join(content.split("\n")[1:]) 
        cleaned_content = re.sub(r"#\w+", "", rest_of_content)
        hashtags_str = " ".join(hashtags)

        tab1, tab2 = st.tabs(["Article", "More"])

        with tab1:
            with st.expander(f"{first_line}", expanded=True):
                st.write(cleaned_content)
                st.write(f"**Hashtags:** {hashtags_str}")
            # Display the relative times
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
    last_gen_time = data['LLM Timestamp'].max().strftime("%H:%M on %d-%m-%Y")

    st.sidebar.success(f"**Total Posts:** *{total_posts}*  \n**Last Post:** *{last_post_time}*  \n**First Post:** *{first_post_time}*  \n**Last Gen:** *{last_gen_time}*")

# Sidebar description
st.sidebar.markdown("""Hello Team Peerr!

This app is a demo frontend for displaying a feed of posts as they get updated. 
The main section shows the latest posts, with each post displaying the publish time, 
an image (open source), and a snippet of the content.
You can expand each post to view the full content. You can also filter by date or tags below.
""")

# Apply cleaning function to 'Hashtags' column
data['Hashtags'] = data['Hashtags'].apply(clean_hashtags)

# Extract unique hashtags and create a multi-select widget
# unique_hashtags = set(sum(data['Hashtags'].tolist(), []))
unique_hashtags = ["#Life Sciences & BioTech", "#Research & Clinical Trials", "#HealthTech & Startups", "#Healthcare & Policy"]
selected_hashtags = st.multiselect("Select Category", options=list(unique_hashtags))

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
            llm_timestamp=row['LLM Timestamp'].strftime("%H:%M on %d-%m-%Y"),
            image_url=row['Image'],
            hashtags=row['Hashtags'],
            content=remove_markdown_formatting(row['Post']),
            model=row['Model'],
            link=row['Link'],
            prompt=row['Prompt'],
            input=row['Input']
        )
