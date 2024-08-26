import streamlit as st
import pandas as pd

# Load the CSV data
df = pd.read_csv("medsii_articles_2.csv")

# Set the title and a description
st.title("Articles Data Viewer")
st.write("""
You can choose to hide or rearrange columns and download the modified dataset.
""")

# Sidebar option to select, hide, and rearrange columns
st.sidebar.header("Column Options")

# Select the columns to display and rearrange them in one step
reordered_columns = st.sidebar.multiselect(
    "Select and Rearrange Columns",
    options=df.columns,
    default=df.columns.tolist()
)

# Reorder the dataframe based on the selected columns
filtered_df = df[reordered_columns]

# Provide an option to download the modified data
@st.cache_data
def convert_df_to_csv(df):
    return df.to_csv(index=False).encode('utf-8')

csv = convert_df_to_csv(filtered_df)

st.download_button(
    label="Download Modified Data as CSV",
    data=csv,
    file_name="modified_medsii_articles.csv",
    mime="text/csv",
)

# Allow the user to select a number of rows to display
num_rows = st.sidebar.slider("Number of Rows to Display", min_value=10, max_value=len(filtered_df), value=10)
st.write(f"Displaying the first {num_rows} out of {len(filtered_df)} rows:")
st.dataframe(filtered_df.head(num_rows))