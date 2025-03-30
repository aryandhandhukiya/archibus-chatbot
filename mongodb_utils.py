import os
from datetime import datetime
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
    """Create a new chat and return its ID"""
    try:
        db = get_db()
        if db is None:
            st.sidebar.warning("Database connection unavailable")
            return None
            
        # Create a new chat document
        now = datetime.now()
        result = db.chats.insert_one({
            "title": title,
            "created_at": now,
            "updated_at": now,
            "messages": []
        })
        
        return str(result.inserted_id) if result.inserted_id else None
    except Exception as e:
        # Log error but don't crash
        print(f"Error creating chat: {str(e)}")
        return None

def save_message(chat_id, role, content, image_urls=None):
    """Save a message to a specific chat"""
    db = get_db()
    if db is None:
        return
        
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now()
    }
    
    if image_urls:
        message["image_urls"] = image_urls
    
    # Update message array
    db.chats.update_one(
        {"_id": ObjectId(chat_id)},
        {
            "$push": {"messages": message},
            "$set": {
                "updated_at": datetime.now(),
                # Update title based on first user message if title is still "New Chat"
                "title": content[:50] + "..." if role == "user" and db.chats.find_one({"_id": ObjectId(chat_id)})["title"] == "New Chat" else db.chats.find_one({"_id": ObjectId(chat_id)})["title"]
            }
        }
    )

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
    """Get a specific chat by ID"""
    db = get_db()
    if db is None:
        return None
        
    return db.chats.find_one({"_id": ObjectId(chat_id)})

def search_chats(query):
    """Search for chats containing the query string"""
    db = get_db()
    if db is None:
        return []
        
    # Search in titles and message content
    pipeline = [
        {
            "$match": {
                "$or": [
                    {"title": {"$regex": query, "$options": "i"}},
                    {"messages.content": {"$regex": query, "$options": "i"}}
                ]
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