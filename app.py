import streamlit as st
import pandas as pd

# Load the data
data = pd.read_csv('databases/llm.csv')

# Convert the Timestamp to datetime
data['Original Timestamp'] = pd.to_datetime(data['Original Timestamp'])
data['LLM Timestamp'] = pd.to_datetime(data['LLM Timestamp'])

# Sort the data by Timestamp, latest at the top
data = data.sort_values(by='Original Timestamp', ascending=False)

# Define the fallback image URL
fallback_image_url = "https://peerr.io/images/logo.svg"  # Consider using a non-SVG format

# Function to validate if the URL is an image URL
def is_valid_image_url(url):
   if not isinstance(url, str):
      return False
   valid_extensions = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg")
    # Strip any query parameters to validate just the file extension
   url_without_query = url.split('?')[0]
    # Check if the URL ends with a valid extension
   if url_without_query.lower().endswith(valid_extensions):
       return url_without_query  # Return the cleaned URL without query parameters
   return False
   # return isinstance(url, str) and url.lower().endswith(valid_extensions)

# Function to create a post
def create_post(timestamp, llm_timestamp, image_url, content):
    image_url = is_valid_image_url(image_url)
    if not image_url:
       image_url = fallback_image_url
        
    # Create two columns for the thumbnail and the published time
    col1, col2 = st.columns([3, 4])
    
    with col1:
        st.image(image_url)
    
    with col2:
        st.warning(f"**Published at** {timestamp}  \n**Generated at** {llm_timestamp}")
        
    # Extract the first line of the content
    if '\n' in content:
        first_line, rest_of_content = content.split('\n', 1)
    else:
        first_line = content[:40]
        rest_of_content = content
    
    # Use the first line in the expander and display the rest of the content inside the expander
    with st.expander(f"{first_line}"):
        st.write(rest_of_content)        
       # st.write(f"Generated from: {link}")
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

st.title("Thoughts Feed Demo")

# Statistics Section
st.sidebar.header("Statistics")
total_posts = len(data)
last_post_time = data['Original Timestamp'].max().strftime("%H:%M on %d-%m-%Y")
last_gen_time = data['LLM Timestamp'].max().strftime("%H:%M on %d-%m-%Y")

st.sidebar.success(f"**Total Posts:** *{total_posts}*  \n**Last Post:** *{last_post_time}*  \n**Last Gen:** *{last_gen_time}*")

# Sidebar description
st.sidebar.header("About This App")
st.sidebar.markdown("""Hello Team Peerr!

This app is a demo frontend for displaying a feed of posts as they get updated. 
The main section shows the latest posts, with each post displaying the publish time, 
an image (with a fallback if none is provided), and a snippet of the content.
You can expand each post to view the full content.
""")

# Create a scrolling feed
for _, row in data.iterrows():
    create_post(
        timestamp=row['Original Timestamp'].strftime("%H:%M on %d-%m-%Y"),
        llm_timestamp=row['LLM Timestamp'].strftime("%H:%M on %d-%m-%Y"),
        image_url=row['Image'],
        content=row['Post'],
    )
