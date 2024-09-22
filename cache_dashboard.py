import streamlit as st
import sqlite3
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Set page config
st.set_page_config(page_title="Cache Dashboard")

# Connect to the database
@st.cache_resource
def get_connection():
    return sqlite3.connect('langcache.db', check_same_thread=False)

conn = get_connection()

# Function to fetch all rows from the database
@st.cache_data
def fetch_data():
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM full_llm_cache')
    return cursor.fetchall()

# Function to calculate costs
def calculate_cost(input_tokens, output_tokens):
    input_cost = (input_tokens * 0.150) / 1_000_000
    output_cost = (output_tokens * 0.600) / 1_000_000
    return input_cost, output_cost, input_cost + output_cost

# Parse LLM data
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

# Parse prompt data
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

# Parse response data
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

# Fetch and process data
rows = fetch_data()
processed_data = []

for i, row in enumerate(rows):
    prompt, llm, _, response = row
    llm_info = parse_llm_data(llm)
    system_message, human_message = parse_prompt_data(prompt)
    response_content, category, hashtags, input_tokens, output_tokens, total_tokens = parse_response_data(response)
    input_cost, output_cost, total_cost = calculate_cost(input_tokens, output_tokens)
    
    processed_data.append({
        'entry_num': i + 1,
        'llm_info': llm_info,
        'system_message': system_message,
        'human_message': human_message,
        'response_content': response_content,
        'category': category,
        'hashtags': hashtags,
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'total_tokens': total_tokens,
        'input_cost': input_cost,
        'output_cost': output_cost,
        'total_cost': total_cost,
    })

# Sidebar
st.sidebar.title("Dashboard Controls")

# Dark mode toggle
if st.sidebar.checkbox("Dark Mode"):
    st.markdown('<style>body {background-color: #1E1E1E; color: #FFFFFF;}</style>', unsafe_allow_html=True)

# Filters
st.sidebar.subheader("Filters")
selected_model = st.sidebar.selectbox("Select Model", options=["All"] + list(set(entry['llm_info'].get('model_name') for entry in processed_data)))
min_cost, max_cost = st.sidebar.slider("Cost Range", 0.0, max(entry['total_cost'] for entry in processed_data), (0.0, max(entry['total_cost'] for entry in processed_data)))

# Apply filters
filtered_data = [
    entry for entry in processed_data
    if (selected_model == "All" or entry['llm_info'].get('model_name') == selected_model)
    and (min_cost <= entry['total_cost'] <= max_cost)
]

# Main content
st.title("Cache Entries Dashboard")

# Overall statistics
total_entries = len(filtered_data)
overall_total_cost = sum(entry['total_cost'] for entry in filtered_data)
total_input_tokens = sum(entry['input_tokens'] for entry in filtered_data)
total_output_tokens = sum(entry['output_tokens'] for entry in filtered_data)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Entries", total_entries)
col2.metric("Total Cost", f"${overall_total_cost:.4f}")
col3.metric("Total Input Tokens", total_input_tokens)
col4.metric("Total Output Tokens", total_output_tokens)

# Visualizations
st.subheader("Visualizations")

# Combined plot: Cost, Tokens, and Model Usage
fig = go.Figure()

# Cost Distribution
cost_df = pd.DataFrame([(entry['entry_num'], entry['input_cost'], entry['output_cost']) for entry in filtered_data],
                       columns=['Entry', 'Input Cost', 'Output Cost'])
fig.add_trace(go.Bar(x=cost_df['Entry'], y=cost_df['Input Cost'], name='Input Cost', marker_color='blue'))
fig.add_trace(go.Bar(x=cost_df['Entry'], y=cost_df['Output Cost'], name='Output Cost', marker_color='red'))

# Token Usage
token_df = pd.DataFrame([(entry['entry_num'], entry['input_tokens'], entry['output_tokens']) for entry in filtered_data],
                        columns=['Entry', 'Input Tokens', 'Output Tokens'])
fig.add_trace(go.Scatter(x=token_df['Entry'], y=token_df['Input Tokens'], name='Input Tokens', yaxis='y2', mode='lines+markers'))
fig.add_trace(go.Scatter(x=token_df['Entry'], y=token_df['Output Tokens'], name='Output Tokens', yaxis='y2', mode='lines+markers'))

# Model Usage
model_counts = pd.Series([entry['llm_info'].get('model_name') for entry in filtered_data]).value_counts()
fig.add_trace(go.Pie(labels=model_counts.index, values=model_counts.values, name='Model Usage', domain={'x': [0.8, 1], 'y': [0, 1]}))

fig.update_layout(
    title='Cost, Tokens, and Model Usage',
    yaxis=dict(title='Cost ($)'),
    yaxis2=dict(title='Tokens', overlaying='y', side='right'),
    barmode='stack',
    height=600
)

st.plotly_chart(fig, use_container_width=True)

# Cache entries
st.subheader("Cache Entries")

# Search functionality
search_query = st.text_input("Search in responses", "")

# Pagination
entries_per_page = st.number_input("Entry per page", min_value=10, max_value=len(filtered_data))
total_pages = (len(filtered_data) - 1) // entries_per_page + 1
page = st.number_input(f"Page (of {total_pages})", min_value=1, max_value=total_pages, value=1)

start_idx = (page - 1) * entries_per_page
end_idx = start_idx + entries_per_page

for i, entry in enumerate(filtered_data[start_idx:end_idx]):
    if search_query.lower() in entry['response_content'].lower():
        with st.expander(f"Cache Entry #{entry['entry_num']}"):
            tabs = st.tabs(["LLM Info", "Prompt", "Response"])
            
            with tabs[0]:
                st.subheader("LLM Information")
                st.write(f"Model Name: {entry['llm_info'].get('model_name', 'N/A')}")
                st.write(f"Temperature: {entry['llm_info'].get('temperature', 'N/A')}")
                st.write(f"Max Retries: {entry['llm_info'].get('max_retries', 'N/A')}")
                
                st.subheader("Costs")
                st.write(f"Input Cost: ${entry['input_cost']:.8f}")
                st.write(f"Output Cost: ${entry['output_cost']:.8f}")
                st.write(f"Total Cost: ${entry['total_cost']:.8f}")
            
            with tabs[1]:
                st.subheader("Prompt Messages")
                st.text_area("System Message", entry['system_message'], height=200, key=f"system_message_{entry['entry_num']}")
                st.text_area("Human Message", entry['human_message'], height=200, key=f"human_message_{entry['entry_num']}")
            
            with tabs[2]:
                st.subheader("Response")
                st.text_area("Content", entry['response_content'], height=400, key=f"response_content_{entry['entry_num']}")
                st.write(f"Category: {entry['category'] if entry['category'] else 'N/A'}")
                st.write(f"Hashtags: {', '.join(entry['hashtags']) if entry['hashtags'] else 'N/A'}")

# Close the connection
conn.close()