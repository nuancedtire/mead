# Import necessary libraries
import streamlit as st
import pandas as pd
import re
import datetime
from dateutil.relativedelta import relativedelta
import yaml
import logging

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
    hashtags = hashtag_string.replace("[", "").replace("]", "").replace("'", "").split(',')
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

@st.cache_data(ttl=3600)  # Cache data for 1 hour
def load_firebase():
    """
    Load data from LLM csv and return it as a Pandas DataFrame.
    """
    data = pd.read_csv('databases/llm.csv')
    data['Time'] = pd.to_datetime(data['Time'])
    data['LLM Timestamp'] = pd.to_datetime(data['LLM Timestamp'])
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
    if not image_url:
        image_url = fallback_image_url
    source = determine_source(link)

    # Create two columns: one for the image and one for post metadata
    col1, col2 = st.columns([3, 5])

    with col1:
        # Use st.image directly to display the image
        st.image(image_url)  # Optionally, you can set a target width
        st.caption(f"Image courtesy [Pexels]({image_url})")

        # Display post metadata
        hashtags_str = " ".join(hashtags[1:])
        st.info(f"*{hashtags_str}*")
        st.write(f"**Published** {relative_time(timestamp)}  \n"
                f"**From:** {source}  \n")

    with col2:
        first_line = content.split("\n")[0] if "\n" in content else content[:40]
        rest_of_content = "\n".join(content.split("\n")[1:])
        cleaned_content = re.sub(r"#\w+", "", rest_of_content)

        tab1, tab2 = st.tabs(["Article", "More"])

        with tab1:
            with st.expander(f"{first_line}", expanded=False):
                st.write(cleaned_content)

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

# Custom CSS to create a scrollable middle column
st.markdown("""
<style>
.main-container {
    display: flex;
    height: 100vh;
}
.column {
    padding: 10px;
    overflow-y: auto;
}
.left-column, .right-column {
    flex: 1;
}
.middle-column {
    flex: 3;
    max-height: 100vh;
    overflow-y: scroll;
}
</style>
""", unsafe_allow_html=True)

# Create a header
st.markdown("<h1 style='text-align: center; color: #4a4a4a;'>Peerr Thoughts</h1>", unsafe_allow_html=True)

# Start the main container
st.markdown('<div class="main-container">', unsafe_allow_html=True)

# Left Column
st.markdown('<div class="column left-column">', unsafe_allow_html=True)
st.subheader("Filters")

# Category selection
selected_label = st.radio("Select Category", options=clean_labels, horizontal=False)
selected_hashtag = f"#{selected_label}"

# Date range selection
st.subheader("Date Range")
start_date = st.date_input("Start Date", value=data['Time'].min().date())
end_date = st.date_input("End Date", value=data['Time'].max().date())

# Search functionality
st.subheader("Search")
search_query = st.text_input("Search posts")

# Refresh button
if st.button("Refresh Data"):
    st.cache_data.clear()
    st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

# Middle Column (Scrollable)
st.markdown('<div class="column middle-column">', unsafe_allow_html=True)

# Filter data
filtered_data = data[(data['Time'].dt.date >= start_date) & (data['Time'].dt.date <= end_date)]
filtered_data = filtered_data[filtered_data['Hashtags'].apply(lambda x: selected_hashtag in x)]
if search_query:
    filtered_data = filtered_data[filtered_data['Post'].str.contains(search_query, case=False)]

# Pagination
if not filtered_data.empty:
    POSTS_PER_PAGE = 5
    total_pages = -(-len(filtered_data) // POSTS_PER_PAGE)
    
    # Align page number input and label horizontally
    col1, col2 = st.columns([2, 3])
    with col1:
        page_number = st.number_input("Page", min_value=1, max_value=total_pages, value=1)
    with col2:
        st.write(f"of {total_pages}")
    
    start_idx = (page_number - 1) * POSTS_PER_PAGE
    end_idx = start_idx + POSTS_PER_PAGE
    
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
else:
    st.write("No posts found for the selected criteria.")

st.markdown('</div>', unsafe_allow_html=True)

# Right Column
st.markdown('<div class="column right-column">', unsafe_allow_html=True)
st.subheader("Statistics")
total_posts = len(data)
last_post_time = data['Time'].max().strftime("%H:%M on %d-%m-%Y")
first_post_time = data['Time'].min().strftime("%H:%M on %d-%m-%Y")
last_gen_time = data['LLM Timestamp'].max().strftime("%H:%M on %d-%m-%Y")

st.markdown(f"""
- **Total Posts:** {total_posts}
- **Last Post:** {last_post_time}
- **First Post:** {first_post_time}
- **Last Generated:** {last_gen_time}
""")

st.subheader("About")
st.markdown("""
This app is a demo frontend for displaying a feed of posts as they get updated.
""")
st.markdown('</div>', unsafe_allow_html=True)

# Close the main container
st.markdown('</div>', unsafe_allow_html=True)

# Footer
st.markdown("---")
st.markdown("<p style='text-align: center;'>Built with ❤️ by Team Peerr</p>", unsafe_allow_html=True)

# Error handling
try:
    st.success("App ran successfully!")
except Exception as e:
    logging.error(f"An error occurred: {str(e)}")
    st.error("An unexpected error occurred. Please check the logs.")
