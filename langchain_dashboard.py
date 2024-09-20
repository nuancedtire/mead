import streamlit as st
import sqlite3
import json
import pandas as pd

# Function to calculate costs
def calculate_cost(input_tokens, output_tokens):
    input_cost = (input_tokens * 0.150) / 1_000_000
    output_cost = (output_tokens * 0.600) / 1_000_000
    return input_cost, output_cost, input_cost + output_cost

# Function to parse LLM data
def parse_llm_data(llm_data):
    llm_json_str = llm_data.split('---')[0]
    try:
        llm_info = json.loads(llm_json_str)
        kwargs = llm_info.get('kwargs', {})
        model_name = kwargs.get('model_name')
        temperature = kwargs.get('temperature')
        max_retries = kwargs.get('max_retries')
        return {'model_name': model_name, 'temperature': temperature, 'max_retries': max_retries}
    except json.JSONDecodeError:
        return {}

# Function to parse prompt data
def parse_prompt_data(prompt_data):
    try:
        prompt_info = json.loads(prompt_data)
        system_message = ''
        human_message = ''
        for message in prompt_info:
            msg_type = message['kwargs'].get('type')
            content = message['kwargs'].get('content', '')
            if msg_type == 'system':
                system_message = content.replace('\\n', '\n')
            elif msg_type == 'human':
                human_message = content.replace('\\n', '\n')
        return system_message, human_message
    except json.JSONDecodeError:
        return '', ''

# Function to parse response data
def parse_response_data(response_data):
    try:
        response_info = json.loads(response_data)
        kwargs = response_info.get('kwargs', {})
        message_info = kwargs.get('message', {})
        content = ''
        usage_metadata = {}
        hashtags = []
        category = ''

        if message_info:
            message_kwargs = message_info.get('kwargs', {})
            content = message_kwargs.get('content', '').strip('"')
            usage_metadata = message_kwargs.get('usage_metadata', {})

            if not content:
                additional_kwargs = message_kwargs.get('additional_kwargs', {})
                if additional_kwargs:
                    tool_calls = additional_kwargs.get('tool_calls', [])
                    for tool_call in tool_calls:
                        tool_args = tool_call.get('function', {}).get('arguments', '{}')
                        tool_args_data = json.loads(tool_args)
                        post_content = tool_args_data.get('post_content', '')
                        if post_content:
                            content = post_content
                            hashtags = tool_args_data.get('hashtags', [])
                            category = tool_args_data.get('category', '')
        else:
            content = kwargs.get('text', '').strip('"')
            usage_metadata = kwargs.get('generation_info', {}).get('usage_metadata', {})

        input_tokens = usage_metadata.get('input_tokens')
        output_tokens = usage_metadata.get('output_tokens')
        total_tokens = usage_metadata.get('total_tokens')

        return content, category, hashtags, input_tokens, output_tokens, total_tokens
    except json.JSONDecodeError:
        return '', '', [], None, None, None

# Streamlit app
def main():
    st.set_page_config(page_title="Langchain Cache Dashboard", layout="wide")
    st.title("Langchain Cache Dashboard")

    # Connect to the cache database
    conn = sqlite3.connect('langcache.db')
    cursor = conn.cursor()

    # Execute a query to fetch all rows from 'full_llm_cache'
    cursor.execute('SELECT * FROM full_llm_cache')
    rows = cursor.fetchall()

    # Initialize total cost
    overall_total_cost = 0

    # Create a list to store all parsed data
    all_data = []

    # Parse all data
    for i, row in enumerate(rows):
        prompt, llm, _, response = row
        llm_info = parse_llm_data(llm)
        system_message, human_message = parse_prompt_data(prompt)
        response_content, category, hashtags, input_tokens, output_tokens, total_tokens = parse_response_data(response)
        input_cost, output_cost, total_cost = calculate_cost(input_tokens, output_tokens)
        overall_total_cost += total_cost

        all_data.append({
            "Entry": i + 1,
            "Model": llm_info.get('model_name'),
            "Temperature": llm_info.get('temperature'),
            "Max Retries": llm_info.get('max_retries'),
            "System Message": system_message[:100] + "...",
            "Human Message": human_message[:100] + "...",
            "Response": response_content[:100] + "...",
            "Category": category,
            "Hashtags": ", ".join(hashtags),
            "Input Tokens": input_tokens,
            "Output Tokens": output_tokens,
            "Total Tokens": total_tokens,
            "Input Cost": input_cost,
            "Output Cost": output_cost,
            "Total Cost": total_cost
        })

    # Convert to DataFrame
    df = pd.DataFrame(all_data)

    # Display overall statistics
    st.header("Overall Statistics")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Entries", len(rows))
    col2.metric("Total Tokens", df['Total Tokens'].sum())
    col3.metric("Total Cost", f"${overall_total_cost:.4f}")

    # Display data table
    st.header("Cache Entries")
    st.dataframe(df)

    # Display detailed information for selected entry
    st.header("Detailed Entry Information")
    selected_entry = st.selectbox("Select an entry to view details", df['Entry'])
    if selected_entry:
        entry_data = df[df['Entry'] == selected_entry].iloc[0]
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("LLM Information")
            st.write(f"Model: {entry_data['Model']}")
            st.write(f"Temperature: {entry_data['Temperature']}")
            st.write(f"Max Retries: {entry_data['Max Retries']}")
        with col2:
            st.subheader("Costs")
            st.write(f"Input Cost: ${entry_data['Input Cost']:.8f}")
            st.write(f"Output Cost: ${entry_data['Output Cost']:.8f}")
            st.write(f"Total Cost: ${entry_data['Total Cost']:.8f}")
        
        st.subheader("Prompt Messages")
        st.text_area("System Message", entry_data['System Message'], height=100)
        st.text_area("Human Message", entry_data['Human Message'], height=100)
        
        st.subheader("Response")
        st.text_area("Content", entry_data['Response'], height=200)
        st.write(f"Category: {entry_data['Category']}")
        st.write(f"Hashtags: {entry_data['Hashtags']}")

    # Close the connection
    conn.close()

if __name__ == "__main__":
    main()