import streamlit as st
import pandas as pd
from datetime import datetime

# Load the data
data = pd.read_csv('databases/llm.csv')

# Convert the Timestamp to datetime
data['Original Timestamp'] = pd.to_datetime(data['Original Timestamp'])

# Sort the data by Timestamp, latest at the top
data = data.sort_values(by='Original Timestamp', ascending=False)

# Define the fallback image URL
fallback_image_url = "https://peerr.io/images/logo.svg"

# Function to validate if the URL is an image URL
def is_valid_image_url(url):
    valid_extensions = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg")
    return isinstance(url, str) and url.lower().endswith(valid_extensions)

# Function to create a post
def create_post(timestamp, image_url, content, link):
    # Validate image URL and use fallback if necessary
    if not is_valid_image_url(image_url):
        image_url = fallback_image_url
    
    # Create two columns for the thumbnail and the published time
    col1, col2 = st.columns([1, 5])
    
    with col1:
        st.image(image_url, width=100)
    
    with col2:
        st.markdown(f"**Publish Time:** {timestamp}")
    
    # Expander for full article content
    with st.expander(f"{content[:50]}..."):
        st.write(content)
        st.markdown(f"Generated from: {link}")

    st.markdown("---")

# Streamlit UI
st.title("Thoughts Feed Demo")

st.markdown("The following posts are updated every 4 hours ")

# Statistics Section
st.sidebar.header("Statistics")
total_posts = len(data)
latest_post_time = data['Original Timestamp'].max().strftime("%Y-%m-%d %H:%M:%S")

st.sidebar.markdown(f"**Total Posts:** {total_posts}")
st.sidebar.markdown(f"**Latest Post:** {latest_post_time}")

# Sidebar description
st.sidebar.header("About This App")
st.sidebar.markdown("""Hello Team Peerr!

This app is a demo frontend for displaying a feed of posts as they get updated. 
The main section shows the latest posts, with each post displaying the publish time, 
an image (with a fallback if none is provided), and a snippet of the content.
You can expand each post to view the full content and see the source link.
""")

# Create a scrolling feed
for _, row in data.iterrows():
    create_post(
        timestamp=row['Original Timestamp'].strftime("%Y-%m-%d %H:%M:%S"),
        image_url=row['Image'],
        content=row['Post'],
        link=row['Link']
    )
