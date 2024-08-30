import csv
import firebase_admin
from firebase_admin import credentials, firestore
import os

# Initialize the Firebase Admin SDK using the credentials file
cred = credentials.Certificate("firebase_creds.json")
firebase_admin.initialize_app(cred)

db = firestore.client()

def upload_csv_to_firebase(csv_file_path):
    collection_name = "scrapegen"  # Replace with your Firestore collection name
    with open(csv_file_path, mode='r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            # Assuming each row has a unique ID field to serve as a document ID
            doc_id = row['LLM Timestamp']  # Replace 'id' with your actual unique ID field name
            db.collection(collection_name).document(doc_id).set(row)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 upload_to_firebase.py <path_to_csv_file>")
        sys.exit(1)
    
    csv_file_path = sys.argv[1]
    upload_csv_to_firebase(csv_file_path)
