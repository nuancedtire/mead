import csv
import firebase_admin
from firebase_admin import credentials, firestore
import os
import sys
from urllib.parse import quote  # For URL encoding
from datetime import datetime  # For handling timestamps
import ast  # For converting string representation of list to an actual list

# Initialize Firebase Admin SDK with provided credentials
def initialize_firebase(cred_path="firebase_creds.json"):
    """
    Initializes Firebase Admin SDK using the credentials JSON file.
    
    Args:
        cred_path (str): Path to the Firebase credentials JSON file.
        
    Returns:
        firestore.Client: Firestore database client.
    """
    try:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        return firestore.client()
    except Exception as e:
        print(f"Error initializing Firebase: {e}")
        sys.exit(1)

# URL encode the Link field and create a new Document ID field
def encode_link_field(row, id_field):
    """
    Encodes the link field to generate a valid Firestore document ID.

    Args:
        row (dict): The current row of CSV data.
        id_field (str): The field from the CSV that contains the Link.
        
    Returns:
        str: The URL-encoded value to be used as the document ID.
    """
    return quote(row[id_field], safe="")  # URL-encode the link (safe="" means no characters are preserved)

# Clean CSV fieldnames by replacing spaces with underscores
def clean_fieldnames(row):
    """
    Cleans the fieldnames by replacing spaces with underscores.

    Args:
        row (dict): The current row of CSV data.

    Returns:
        dict: The row with cleaned fieldnames.
    """
    return {key.replace(" ", "_"): value for key, value in row.items()}

# Convert timestamp string to Firestore-compatible timestamp
def convert_to_timestamp(value):
    """
    Converts a string timestamp in the format 'YYYY-MM-DD HH:MM:SS' to a Firestore-compatible datetime object.

    Args:
        value (str): The string representation of the timestamp.

    Returns:
        datetime: A Python datetime object for Firestore.
    """
    try:
        return datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        print(f"Error: Invalid timestamp format for value '{value}'")
        return None

# Convert the hashtags string representation to a Python list
def convert_to_list(value):
    """
    Converts a string representation of a list to an actual Python list.

    Args:
        value (str): The string representation of a list.

    Returns:
        list: The actual Python list object.
    """
    try:
        return ast.literal_eval(value) if isinstance(value, str) else value
    except (ValueError, SyntaxError):
        print(f"Error: Unable to convert '{value}' to a list")
        return []

# Upload data from a CSV file to Firestore
def upload_csv_to_firebase(csv_file_path, db, collection_name, id_field="Link", encoded_id_field="EncodedLink"):
    """
    Uploads data from a CSV file to a Firestore collection.

    Args:
        csv_file_path (str): Path to the CSV file.
        db (firestore.Client): Firestore database client.
        collection_name (str): The name of the Firestore collection where data will be uploaded.
        id_field (str): The field from the CSV that will be used to generate the encoded document ID.
        encoded_id_field (str): The new field in Firestore to store encoded link.
    
    Raises:
        FileNotFoundError: If the CSV file is not found.
        KeyError: If the id_field is missing in the CSV.
    """
    try:
        with open(csv_file_path, mode='r') as file:
            reader = csv.DictReader(file)
            if id_field not in reader.fieldnames:
                raise KeyError(f"ID field '{id_field}' not found in CSV headers")

            for row in reader:
                # Clean the field names by replacing spaces with underscores
                row = clean_fieldnames(row)

                # Generate a new document ID based on the encoded link field
                doc_id = encode_link_field(row, id_field.replace(" ", "_"))  # Also remove spaces from the id_field

                # Convert specific columns
                if 'Time' in row:
                    row['Time'] = convert_to_timestamp(row['Time'])
                if 'LLM_Timestamp' in row:  # Assuming 'LLM_Timestamp' after cleaning
                    row['LLM_Timestamp'] = convert_to_timestamp(row['LLM_Timestamp'])
                if 'Hashtags' in row:
                    row['Hashtags'] = convert_to_list(row['Hashtags'])

                # Optionally, add the encoded ID back into the document data under a new field
                row[encoded_id_field] = doc_id

                # Upload the row as a document in the Firestore collection, using the encoded doc_id
                db.collection(collection_name).document(doc_id).set(row)
            print(f"Data successfully uploaded to Firestore collection: {collection_name}")
    
    except FileNotFoundError:
        print(f"Error: File not found at path {csv_file_path}")
        sys.exit(1)
    except KeyError as ke:
        print(f"Error: {ke}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error while uploading data: {e}")
        sys.exit(1)

# Main function to parse arguments and initiate upload
def main():
    """
    Main function to parse command-line arguments and initiate the CSV upload process.
    
    Expects a single argument: the path to the CSV file.
    """
    if len(sys.argv) != 2:
        print("Usage: python3 upload_to_firebase.py <path_to_csv_file>")
        sys.exit(1)

    csv_file_path = sys.argv[1]
    
    # Initialize Firestore client
    db = initialize_firebase()

    # Set Firestore collection name and CSV's ID field
    collection_name = "scraper-09-11-24"  # Modify as needed
    id_field = "Link"  # Field containing the links in the CSV
    encoded_id_field = "Encoded_Link"  # New field to store encoded link in Firestore

    # Upload data to Firestore
    upload_csv_to_firebase(csv_file_path, db, collection_name, id_field, encoded_id_field)

if __name__ == "__main__":
    main()