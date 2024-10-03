import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import logging

# Initialize Firebase Admin SDK
cred = credentials.Certificate("firebase_credentials.json")
firebase_admin.initialize_app(cred)

# Get Firestore client
db = firestore.client()

def setup_logger():
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')

def copy_collection(source_collection, destination_collection):
    # Get all documents from the source collection
    docs = db.collection(source_collection).get()
    
    # Counter for successful copies
    successful_copies = 0
    
    for doc in docs:
        try:
            # Get the document data
            data = doc.to_dict()
            
            # Add the document to the destination collection with the same ID
            db.collection(destination_collection).document(doc.id).set(data)
            
            successful_copies += 1
            logging.info(f"Successfully copied document {doc.id}")
        except Exception as e:
            logging.error(f"Error copying document {doc.id}: {str(e)}")
    
    logging.info(f"Copied {successful_copies} out of {len(docs)} documents")

def main():
    setup_logger()
    
    source_collection = "llm"
    destination_collection = "llm_test"
    
    logging.info(f"Starting to copy from {source_collection} to {destination_collection}")
    copy_collection(source_collection, destination_collection)
    logging.info("Copy process completed")

if __name__ == "__main__":
    main()