import sys
import os

# Add parent directory to path to import mongodb_utils
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from mongodb_utils import setup_indexes, get_db

def initialize_mongodb():
    """Initialize MongoDB collections and indexes"""
    print("Connecting to MongoDB...")
    db = get_db()
    if db is not None:
        # Ensure collections exist
        if "chats" not in db.list_collection_names():
            db.create_collection("chats")
            print("Created chats collection")
        else:
            print("Chats collection already exists")
        
        # Create indexes
        print("Setting up indexes...")
        setup_indexes()
        print("Created indexes for better performance")
        
        print("MongoDB setup complete!")
    else:
        print("Failed to connect to MongoDB")

if __name__ == "__main__":
    initialize_mongodb()