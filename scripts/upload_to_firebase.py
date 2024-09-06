import csv
import firebase_admin
from firebase_admin import credentials, firestore
import os
import sys

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

# Upload data from a CSV file to Firestore
def upload_csv_to_firebase(csv_file_path, db, collection_name, id_field="LLM Timestamp"):
    """
    Uploads data from a CSV file to a Firestore collection.

    Args:
        csv_file_path (str): Path to the CSV file.
        db (firestore.Client): Firestore database client.
        collection_name (str): The name of the Firestore collection where data will be uploaded.
        id_field (str): The field from the CSV that will be used as the document ID in Firestore.

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
                # Use the specified ID field from the CSV as the document ID
                doc_id = row[id_field]
                # Upload the row as a document in the Firestore collection
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
    collection_name = "scraper-06-11-24"  # Modify as needed
    id_field = "LLM Timestamp"  # Modify as needed (ensure this field exists in your CSV)

    # Upload data to Firestore
    upload_csv_to_firebase(csv_file_path, db, collection_name, id_field)

if __name__ == "__main__":
    main()
