import streamlit as st
import pandas as pd

data = pd.read_csv('databases/llm.csv')
# Load the additional CSV files
meds = pd.read_csv('databases/meds.csv')
sifted = pd.read_csv('databases/sifted.csv')
scape = pd.read_csv('databases/scape.csv')

# Convert the Timestamp to datetime
data['Time'] = pd.to_datetime(data['Time'])
data['LLM Timestamp'] = pd.to_datetime(data['LLM Timestamp'])

# Sort the data by Timestamp, latest at the top
data = data.sort_values(by='Time', ascending=False)

# Define the fallback image URL
fallback_image_url = "https://peerr.io/images/logo.svg"  # Consider using a non-SVG format

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

# Function to create a post
def create_post(timestamp, llm_timestamp, hashtags, image_url, content, model, link, prompt):
    if not image_url:
        image_url = fallback_image_url
    source = determine_source(link)
        
    # Create two columns for the thumbnail and the published time
    col1, col2 = st.columns([3, 5])
    
    with col1:
        st.image(f"{image_url}?auto=compress&cs=tinysrgb&fit=crop&h=360&w=640", use_column_width=True)
    
    with col2:
        st.info(f"**Published at:** {timestamp}  \n**Generated at:** {llm_timestamp}  \n**From:** {source}")
        with st.expander(f"*{model}*"):
        #    st.write(f"{prompt}")
        
            # Extract the first line of the content
            if "\n" in content:
                first_line, rest_of_content = content.split('\n', 1)
            else:
                first_line = content[:40]
                rest_of_content = content
    
    with st.expander(f"{first_line}"):
        st.write(rest_of_content)
    
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

with st.sidebar:

    # Statistics Section
    total_posts = len(data)
    last_post_time = data['Time'].max().strftime("%H:%M on %d-%m-%Y")
    last_gen_time = data['LLM Timestamp'].max().strftime("%H:%M on %d-%m-%Y")

    st.sidebar.success(f"**Total Posts:** *{total_posts}*  \n**Last Post:** *{last_post_time}*  \n**Last Gen:** *{last_gen_time}*")

# Sidebar description
st.sidebar.markdown("""Hello Team Peerr!

This app is a demo frontend for displaying a feed of posts as they get updated. 
The main section shows the latest posts, with each post displaying the publish time, 
an image (with a fallback if none is provided), and a snippet of the content.
You can expand each post to view the full content. You can also filter by date below.
""")

# Date Filter in Sidebar
st.sidebar.header("Filter by Date")
start_date = st.sidebar.date_input("Start Date", value=data['Time'].min().date())
end_date = st.sidebar.date_input("End Date", value=data['Time'].max().date())

# Hashtag Filter in Sidebar
st.sidebar.header("Filter by Hashtags")

# Apply the cleaning function to the Hashtags column
data['Hashtags'] = data['Hashtags'].apply(clean_hashtags)

# Extract unique hashtags
unique_hashtags = set(sum(data['Hashtags'].tolist(), []))

# Create a multi-select widget
selected_hashtags = st.sidebar.multiselect("Select Hashtags", options=list(unique_hashtags))

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
            content=row['Post'],
            model=row['Model'],
            link=row['Link'],
            prompt=row['Prompt']
        )