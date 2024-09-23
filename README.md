# Peerr Thoughts

Peerr Thoughts is a sophisticated web application that aggregates, processes, and displays healthcare-related news and insights. It uses advanced AI techniques to generate engaging social media posts from various medical and healthcare news sources.

## Table of Contents

1. [Features](#features)
2. [Installation](#installation)
3. [Usage](#usage)
4. [Project Structure](#project-structure)
5. [Configuration](#configuration)
6. [Deployment](#deployment)

## Features

- Scrapes healthcare news from multiple sources (Medsii, Sifted, Medscape, NICE UK)
- Processes articles using GPT-4 to generate engaging social media posts
- Generates relevant images using Fal AI
- Displays posts in a user-friendly Streamlit interface
- Filters posts by category, hashtags, and sources
- Caches LLM responses for improved performance
- Provides a cache dashboard for monitoring API usage and costs

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/your-username/peerr-thoughts.git
   cd peerr-thoughts
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up your environment variables:
   - Create a `.env` file in the root directory
   - Add your OpenAI API key: `OPENAI_API_KEY=your_api_key_here`
   - Add your Fal AI key: `FAL_KEY=your_fal_ai_key_here`

## Usage

1. Run the scrapers to fetch the latest news:
   ```
   python run_scrapers.py
   ```

2. Start the Streamlit app:
   ```
   streamlit run app.py
   ```

3. Access the application in your web browser at `http://localhost:8501`

4. To view the cache dashboard:
   ```
   streamlit run cache_dashboard.py
   ```

## Project Structure

- `app.py`: Main Streamlit application
- `cache_dashboard.py`: Dashboard for monitoring LLM cache and costs
- `config.py`: Configuration settings for the application
- `run_scrapers.py`: Script to run all scrapers
- `scripts/`:
  - `update_meds.py`: Scraper for Medsii
  - `update_sifted.py`: Scraper for Sifted
  - `update_scape.py`: Scraper for Medscape
  - `update_nice.py`: Scraper for NICE UK
  - `llm.py`: LLM processing script
- `databases/`: CSV files for storing scraped and processed data
- `logs/`: Log files for each scraper and the LLM process
- `Dockerfile`: Docker configuration for containerization

## Configuration

The main configuration settings can be found in `config.py`. This file includes `system_prompt`:

```python:config.py
You are a content strategist specializing in crafting engaging and informative social media posts for healthcare professionals based on detailed medical articles or web content. Your task is to create ready-to-use social media posts that accurately summarize key points in a way that is relevant and thought-provoking.

Guidelines:

 - Engaging Openers: Start with a creative hook that grabs attention—use clinical scenarios, surprising statistics, or thought-provoking questions (without relying on overused phrases like “Did you know?”).
 - Informative Content: Provide a concise yet comprehensive summary of the most important information, ensuring clarity and relevance to healthcare professionals.
 - Balanced Tone: Maintain a professional yet approachable tone. Use varied sentence structures and a conversational feel that resonates with your audience.
 - Highlight Key Findings: Use bullet points to present important statistics or findings, making the information easy to read and digest.
 - Foster Engagement: Conclude with a thoughtful question or statement that encourages reflection or invites interaction, ensuring it feels natural and appropriate.
 - Emojis Usage: Use emojis sparingly and strategically to emphasize key points or statistics, while maintaining professionalism.
 - Formatting: Deliver the final post as plain text, formatted for easy reading without the need for Markdown or HTML.

Key Focus:

 - Clarity and Comprehensiveness: Ensure the post covers essential details to inform healthcare professionals effectively.
 - Readability: Use bullet points and varied sentence lengths to enhance readability.

An Example Post:

⏱️ A weekly insulin dose that matches daily treatments in efficacy—could this reshape type 2 diabetes care?

In the QWINT-2 phase 3 trial, once-weekly insulin efsitora alfa demonstrated:

 - A1C reduction of 1.34% vs. 1.26% with daily insulin degludec, resulting in A1C levels of 6.87% and 6.95% respectively at 52 weeks.
 - 45 minutes more time in range per day without increased hypoglycemia risk.
 - A safety profile similar to daily insulins, with no severe hypoglycemic events reported for efsitora.

Could once-weekly dosing improve adherence and reduce treatment burden for your patients?
```

Modify these settings to adjust the LLM behavior, categories, and hashtags used in the application.

## Deployment

The application can be deployed using Docker. A Dockerfile is provided in the repository.

1. Build the Docker image:
   ```
   docker build -t peerr-thoughts .
   ```

2. Run the container:
   ```
   docker run -p 8080:8080 peerr-thoughts
   ```

The application will be accessible at `http://localhost:8080`.

---

For more information or support, please contact Faz.
