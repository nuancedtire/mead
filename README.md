# Peerr Thoughts

Peerr Thoughts is a sophisticated web application that aggregates, processes, and displays healthcare-related news and insights. It uses advanced AI techniques to generate engaging social media posts from various medical and healthcare news sources.

## Table of Contents

1. [Features](#features)
2. [Installation](#installation)
3. [Usage](#usage)
4. [Project Structure](#project-structure)
5. [Configuration](#configuration)
6. [Deployment](#deployment)
7. [Contributing](#contributing)
8. [License](#license)

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

The main configuration settings can be found in `config.py`. This file includes:

```python:config.py
startLine: 1
endLine: 137
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
