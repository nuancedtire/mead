# Use the official Python image as the base image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install the required packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Expose the ports that Streamlit and FastAPI will run on
EXPOSE 8080 8000

# Set the command to run both the Streamlit app and the FastAPI server
CMD ["sh", "-c", "streamlit run app.py --server.port 8080 --server.address 0.0.0.0 & uvicorn scripts.api:app --host 0.0.0.0 --port 8000"]