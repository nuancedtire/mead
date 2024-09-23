# Import necessary libraries
import streamlit as st
import pandas as pd
import re
import datetime
from dateutil.relativedelta import relativedelta
import yaml
import logging
from streamlit_extras.metric_cards import style_metric_cards
from streamlit_extras.stoggle import stoggle

# Add these functions back into the main file
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
    hashtags = hashtag_string.replace("[", "").replace("]", "").replace("#", "").replace("'", "").split(',')
    return [f"#{tag.strip()}" for tag in hashtags]

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
@st.cache_data
def load_meds_data():
    return pd.read_csv('databases/meds.csv')   # Medsii data

@st.cache_data
def load_sifted_data():
    return pd.read_csv('databases/sifted.csv')  # Sifted data

@st.cache_data
def load_scape_data():
    return pd.read_csv('databases/scape.csv')  # Medscape data

@st.cache_data
def load_nice_data():
    return pd.read_csv('databases/nice.csv')  # Nice data

@st.cache_data(ttl=3600)  # Cache data for 1 hour
def load_firebase():
    """
    Load data from LLM csv and return it as a Pandas DataFrame.
    """
    data = pd.read_csv('databases/llm.csv')
    data['Time'] = pd.to_datetime(data['Time'], format='mixed')
    data['LLM Timestamp'] = pd.to_datetime(data['LLM Timestamp'], format='mixed')
    data = data.sort_values(by='Time', ascending=False)
    return data

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
    elif link in nice['Link'].values:
        return "NICE UK"
    else:
        return "Unknown Source"

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
    is_fallback_image = False
    if not isinstance(image_url, str) or not image_url:
        image_url = fallback_image_url
        is_fallback_image = True
    source = determine_source(link)

    # Create two columns: one for the image and one for post metadata
    col1, col2 = st.columns([3, 5])

    with col1:
        # Use st.image directly to display the image
        st.image(image_url)  # Optionally, you can set a target width
        if is_fallback_image:
            st.caption("Fallback image")
        else:
            if "pexels.com" in image_url:
                st.caption(f"Image courtesy [Pexels]({image_url})")
            elif "fal.media" in image_url:
                st.caption(f"Image courtesy [Peerr AI]({image_url})")
            else:
                st.caption(f"Image source: {image_url}")
        
        # Display hashtags and published details below the image
        hashtags_str = ", ".join(hashtags[1:])
        st.info(f"*{hashtags_str}*")
        st.write(f"**Published** {relative_time(timestamp)}  \n"
                f"**From:** {source}  \n")

    with col2:
        first_line = content.split("\n")[0] if "\n" in content else content[:40]
        rest_of_content = "\n".join(content.split("\n")[1:])
        cleaned_content = re.sub(r"#\w+", "", rest_of_content)

        tab1, tab2 = st.tabs(["Article", "More"])

        with tab1:
            with st.expander(f"{first_line}", expanded=True):
                st.write(cleaned_content)

        with tab2:
            st.write(link)
            st.write(content)
            st.write(hashtags)
            stoggle("Show Input", input)

    # Add a horizontal line between posts
    st.markdown("---")

# Streamlit UI configuration
st.set_page_config(page_title="Peerr Thoughts", page_icon="💭", layout="wide")

# Custom CSS with Peerr color scheme and gradient
st.markdown("""
    <style>
    .stApp {
        background-color: #FFFFFF;
    }
    .stSidebar {
        background-color: #F0F2F6;
    }
    .stButton>button {
        color: #FFFFFF;
        background: linear-gradient(90deg, #FF9966 0%, #FF6699 100%);
        border: none;
    }
    .stButton>button:hover {
        color: #FFFFFF;
        background: linear-gradient(90deg, #FF8855 0%, #FF5588 100%);
        border: none;
    }
    .stTextInput>div>div>input {
        color: #262730;
    }
    .stSelectbox>div>div>select {
        color: #262730;
    }
    h1, h2, h3 {
        background: linear-gradient(90deg, #FF9966 0%, #FF6699 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .main-title {
        font-size: 2.5rem;
        font-weight: bold;
        margin-top: 0;
        text-align: left;
        background: linear-gradient(90deg, #FF9966 0%, #FF6699 30%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    </style>
    """, unsafe_allow_html=True)

# Main content
st.markdown('<h1 class="main-title">Peerr Thoughts</h1>', unsafe_allow_html=True)

# Load the data
meds = load_meds_data()
sifted = load_sifted_data()
scape = load_scape_data()
nice = load_nice_data()
data = load_firebase()

# Apply cleaning function to 'Hashtags' column
data['Hashtags'] = data['Hashtags'].apply(clean_hashtags)

# List of hashtags with # symbols
unique_hashtags = ["#All", "#Life Sciences & BioTech", "#Research & Clinical Trials", "#HealthTech & Startups", "#Healthcare & Policy"]
clean_labels = [tag[1:] for tag in unique_hashtags]

# Move category selection to the main screen
selected_label = st.radio("📊 Select a Category", options=clean_labels, horizontal=True)
selected_hashtag = f"#{selected_label}" if selected_label != "All" else None

# Sidebar
with st.sidebar:
    st.sidebar.markdown('<h3>Filters</h3>', unsafe_allow_html=True)
    
    # Add multiselect for hashtags
    all_hashtags = sorted(set([tag for tags in data['Hashtags'] for tag in tags]))
    selected_hashtags = st.multiselect("#️⃣ Filter by Hashtags", options=all_hashtags)
    
    # Add multiselect for sources
    all_sources = ["Medsii", "Sifted", "Medscape", "NICE UK", "Unknown"]
    selected_sources = st.multiselect("🌐 Filter by Source", options=all_sources)
    
    search_query = st.text_input("🔎 Search posts")
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("📅 Start Date", value=data['Time'].min().date())
    with col2:
        end_date = st.date_input("📅 End Date", value=data['Time'].max().date())
    
    st.button("🔄 Refresh Data", on_click=lambda: (st.cache_data.clear(), st.rerun()))
    
    total_posts = len(data)
    last_post = data['Time'].max().strftime("%d %b")
    first_post = data['Time'].min().strftime("%d %b")
    last_gen = data['LLM Timestamp'].max().strftime("%d %b")
    
    st.subheader("Statistics")
    col1, col2 = st.columns(2)
    col1.metric("Total Posts", total_posts)
    col1.metric("Oldest Post", first_post)
    col2.metric("Latest Post", last_post)
    col2.metric("Last Generated", last_gen)
    
    style_metric_cards(
        background_color="#FFFFFF",
        border_size_px=1,
        border_color="#E0E0E0",
        border_radius_px=5,
        border_left_color="#FF9966",  # Using the orange color from the gradient
        box_shadow=True,
    )

# Initialize session state for page number if it doesn't exist
if 'page_number' not in st.session_state:
    st.session_state.page_number = 1

# Main content area
# Filter data
filtered_data = data[(data['Time'].dt.date >= start_date) & (data['Time'].dt.date <= end_date)]

if selected_hashtag:
    filtered_data = filtered_data[filtered_data['Hashtags'].apply(lambda x: selected_hashtag in x)]

# Add filtering by selected hashtags
if selected_hashtags:
    filtered_data = filtered_data[filtered_data['Hashtags'].apply(lambda x: any(tag in x for tag in selected_hashtags))]

# Add filtering by selected sources
if selected_sources:
    filtered_data = filtered_data[filtered_data['Link'].apply(lambda x: determine_source(x) in selected_sources)]

if search_query:
    filtered_data = filtered_data[filtered_data['Post'].str.contains(search_query, case=False)]

# Pagination
if not filtered_data.empty:
    # Initialize posts per page in session state if it doesn't exist
    if 'posts_per_page' not in st.session_state:
        st.session_state.posts_per_page = 5

    # Top pagination and posts per page input
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    with col3:
        new_posts_per_page = st.number_input(
            "Posts per page",
            min_value=1,
            max_value=50,
            value=st.session_state.posts_per_page,
            key="top_posts_per_page"
        )
    
    total_pages = -(-len(filtered_data) // st.session_state.posts_per_page)
    
    with col2:
        new_page_number = st.number_input(
            f"Page (total: {total_pages})", 
            min_value=1, 
            max_value=total_pages, 
            value=st.session_state.page_number,
            key="top_page_number"
        )
    
    # Check if either posts per page or page number has changed
    if new_posts_per_page != st.session_state.posts_per_page or new_page_number != st.session_state.page_number:
        st.session_state.posts_per_page = new_posts_per_page
        st.session_state.page_number = new_page_number
        st.rerun()

    start_idx = (st.session_state.page_number - 1) * st.session_state.posts_per_page
    end_idx = start_idx + st.session_state.posts_per_page
    
    for _, row in filtered_data.iloc[start_idx:end_idx].iterrows():
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

    # Add bottom pagination
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    with col3:
        new_bottom_posts_per_page = st.number_input(
            "Posts per page",
            min_value=1,
            max_value=50,
            value=st.session_state.posts_per_page,
            key="bottom_posts_per_page"
        )
    with col2:
        new_bottom_page_number = st.number_input(
            f"Page (total: {total_pages})", 
            min_value=1, 
            max_value=total_pages, 
            value=st.session_state.page_number, 
            key="bottom_page_number"
        )
    
    # Check if either posts per page or page number has changed
    if new_bottom_posts_per_page != st.session_state.posts_per_page or new_bottom_page_number != st.session_state.page_number:
        st.session_state.posts_per_page = new_bottom_posts_per_page
        st.session_state.page_number = new_bottom_page_number
        st.rerun()
else:
    st.write("No posts found for the selected criteria.")


st.markdown("<p style='text-align: center;'>Built with ❤ by Faz</p>", unsafe_allow_html=True)
