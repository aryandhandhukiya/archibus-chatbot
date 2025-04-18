import os
from datetime import datetime
import traceback
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import streamlit as st
from bson.objectid import ObjectId

def get_mongo_client():
    """Get MongoDB client with improved error handling"""
    if "mongo_client" not in st.session_state:
        try:
            # ONLY get connection string from secrets
            if "mongodb" in st.secrets and "uri" in st.secrets.mongodb:
                connection_string = st.secrets.mongodb.uri
            else:
                # For development only, provide a helpful error
                st.error("MongoDB connection string not found in secrets")
                print("Error: MongoDB URI not found in secrets.toml")
                return None
            
            # Use more compatible connection parameters
            st.session_state.mongo_client = MongoClient(
                connection_string,
                ssl=True,
                tlsAllowInvalidCertificates=True,
                connectTimeoutMS=10000,
                socketTimeoutMS=10000,
                serverSelectionTimeoutMS=10000
            )
            
            # Quick test connection
            st.session_state.mongo_client.admin.command('ping', serverSelectionTimeoutMS=5000)
            
        except Exception as e:
            st.session_state.mongo_client = None
            st.sidebar.error(f"MongoDB connection error: {str(e)}")
            return None
    
    return st.session_state.mongo_client

def get_db():
    """Get database instance"""
    client = get_mongo_client()
    if client:
        return client.archibus_chatbot
    return None

def delete_chat(chat_id):
    """Delete a chat by ID"""
    db = get_db()
    if db is None:
        return False
        
    result = db.chats.delete_one({"_id": ObjectId(chat_id)})
    return result.deleted_count > 0

def create_new_chat(title="New Chat"):
    """Create a new chat with better error handling."""
    try:
        db = get_db()
        if db is None:
            print("Database connection failed")
            return None
            
        chats_collection = db['chats']
        
        # Create new chat document with empty messages array
        new_chat = {
            "title": title,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "messages": []  # Make sure this is initialized as an empty array
        }
        
        result = chats_collection.insert_one(new_chat)
        
        if result.inserted_id:
            print(f"Created new chat with ID: {result.inserted_id}")
            return str(result.inserted_id)
        else:
            print("Failed to create new chat")
            return None
            
    except Exception as e:
        print(f"Error creating new chat: {str(e)}")
        traceback.print_exc()
        return None

def save_message(chat_id: str, message: dict) -> bool:
    """Save a message to an existing chat."""
    try:
        print(f"Saving message to chat ID: {chat_id}")
        db = get_db()
        if not db:
            return False
            
        # Update chat with new message and timestamp
        result = db.chats.update_one(
            {"_id": ObjectId(chat_id)},
            {
                "$push": {"messages": message},  # Use message instead of message_data
                "$set": {"updated_at": datetime.now()}
            }
        )
        
        if result.modified_count > 0:
            print(f"Message saved to chat {chat_id}")
            return True
        else:
            print(f"Failed to save message - chat not found: {chat_id}")
            
            # Debug: Try to find the chat
            chat = db.chats.find_one({"_id": ObjectId(chat_id)})  # Use db.chats instead of chats_collection
            if chat:
                print(f"Chat exists but update failed")
            else:
                print(f"No chat found with ID {chat_id}")
                
            return False
    
    except Exception as e:
        print(f"Error saving message: {e}")
        return False

def get_chat_list():
    """Get list of all chats"""
    db = get_db()
    if db is None:
        return []
        
    return list(db.chats.find({}, {
        "title": 1, 
        "created_at": 1, 
        "updated_at": 1
    }).sort("updated_at", -1))

def get_chat_by_id(chat_id):
    """Get a chat by its ID with debug information."""
    try:
        print(f"Attempting to find chat with ID: {chat_id}, type: {type(chat_id)}")
        db = get_db()
        if db is None:
            print("Database connection failed")
            return None
            
        chats_collection = db['chats']
        
        # Try with string ID first
        chat = chats_collection.find_one({"_id": chat_id})
        if chat:
            print(f"Found chat using raw ID: {chat_id}")
            return chat
        
        # Try with ObjectId
        try:
            from bson.objectid import ObjectId
            obj_id = ObjectId(chat_id)
            print(f"Converted to ObjectId: {obj_id}")
            chat = chats_collection.find_one({"_id": obj_id})
            if chat:
                print(f"Found chat using ObjectId: {obj_id}")
                return chat
            else:
                print(f"No chat found with ObjectId: {obj_id}")
        except Exception as e:
            print(f"Error with ObjectId conversion: {str(e)}")
        
        print(f"Chat not found with any method for ID: {chat_id}")
        return None
    except Exception as e:
        print(f"Error in get_chat_by_id: {str(e)}")
        return None
    

def search_chats(query):
    """Search for chats containing the query string in title only"""
    db = get_db()
    if db is None:
        return []
        
    # Search in titles only (removed messages.content search)
    pipeline = [
        {
            "$match": {
                "title": {"$regex": query, "$options": "i"}
            }
        },
        {
            "$project": {
                "title": 1, 
                "created_at": 1, 
                "updated_at": 1
            }
        },
        {"$sort": {"updated_at": -1}}
    ]
    
    return list(db.chats.aggregate(pipeline))


def setup_indexes():
    """Setup MongoDB indexes for better performance"""
    db = get_db()
    if db is None:
        return
        
    # Create indexes
    db.chats.create_index("title")
    db.chats.create_index("created_at")
    db.chats.create_index("updated_at")
    db.chats.create_index([("messages.content", "text")])