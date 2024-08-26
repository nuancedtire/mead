import streamlit as st
import pandas as pd

# Load the CSV data
df = pd.read_csv("medsii-articles-csv.csv")

# Set the title and a description
st.title("Articles Data Viewer")
st.write("""
Use the filters to narrow down the data and explore specific details. You can also download the filtered data.
""")

# Display the full dataframe with the option to expand
with st.expander("View Full Dataset"):
    st.dataframe(df)

# Filter the data based on user input
st.sidebar.header("Filter Options")

# Dynamically create filters based on unique values in the columns
columns_to_filter = st.sidebar.multiselect(
    "Select Columns to Filter",
    df.columns,
    default=[]
)

filtered_df = df.copy()
for column in columns_to_filter:
    unique_values = df[column].unique()
    selected_values = st.sidebar.multiselect(f"Filter by {column}", unique_values, default=unique_values)
    filtered_df = filtered_df[filtered_df[column].isin(selected_values)]

# Display the filtered dataframe
st.subheader("Filtered Data")
st.write(f"Showing {len(filtered_df)} out of {len(df)} records")
st.dataframe(filtered_df)

# Provide an option to download the filtered data
@st.cache_data
def convert_df_to_csv(df):
    return df.to_csv(index=False).encode('utf-8')

csv = convert_df_to_csv(filtered_df)

st.download_button(
    label="Download Filtered Data as CSV",
    data=csv,
    file_name="filtered_medsii_articles.csv",
    mime="text/csv",
)

# Add a few more features for better interaction
st.sidebar.markdown("### Additional Options")

# Allow the user to select a number of rows to display
num_rows = st.sidebar.slider("Number of Rows to Display", min_value=10, max_value=len(filtered_df), value=10)
st.write(f"Displaying the first {num_rows} rows:")
st.dataframe(filtered_df.head(num_rows))

# Display some statistics or insights (you can customize this based on your data)
st.sidebar.markdown("### Data Insights")
st.write("Basic Statistics of the Dataset:")
st.write(filtered_df.describe(include='all'))
