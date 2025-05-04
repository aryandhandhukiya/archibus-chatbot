import streamlit as st
from chatbot.response_generator import generate_response
from datetime import datetime, timedelta
from mongodb_utils import (
    create_new_chat,
    save_message,
    get_chat_list,
    get_chat_by_id,
    search_chats,
    delete_chat,
    get_db
)
import base64
from io import BytesIO
from PIL import Image
import re

st.set_page_config(page_title="Archibus AI", layout="wide")

# ✅ Ensure Session State Variables Exist
if "messages" not in st.session_state:
    st.session_state.messages = []

if "language" not in st.session_state:
    st.session_state.language = "Japanese"

if "current_chat_id" not in st.session_state:
    st.session_state.current_chat_id = None

if "search_query" not in st.session_state:
    st.session_state.search_query = ""

if "feedback_key" not in st.session_state:
    st.session_state.feedback_key = 0

if "needs_regeneration" not in st.session_state:
    st.session_state.needs_regeneration = False
if "regeneration_prompt" not in st.session_state:
    st.session_state.regeneration_prompt = None
if "regeneration_index" not in st.session_state:
    st.session_state.regeneration_index = None

# ✅ Custom Navbar and Styling
st.markdown(
    """
    <style>
        /* Hide Streamlit elements */
        .stDeployButton,
        .viewerBadge_container__1QSob,
        #manage-app-button,
        footer,
        .viewerBadge_link__1S137,
        #MainMenu,
        div[data-testid="stToolbar"],
        button[title="View fullscreen"],
        button[title="Download"],
        button[title="Share"],
        button[title="View source"],
        button[title="Edit source"],
        button[title="Star"] {
            display: none !important;
            visibility: hidden !important;
        }

        /* Keep the three-dot menu visible */
        button[data-testid="stAppViewerMenuButton"] {
            display: inline-flex !important;
            visibility: visible !important;
        }

        /* Style adjustments for navbar */
        .navbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.75rem 1.5rem;
            background-color: #121212;
            color: white;
            border-bottom: 1px solid #333;
        }

        .navbar-title {
            font-size: 20px;
            font-weight: bold;
        }

        /* Chat history styling */
        .chat-item {
            padding: 8px 12px;
            margin-bottom: 5px;
            border-radius: 4px;
            cursor: pointer;
            transition: background-color 0.2s;
        }

        .chat-item:hover {
            background-color: rgba(49, 51, 63, 0.1);
        }

        .chat-date {
            font-size: 0.75rem;
            color: #666;
            margin-top: 2px;
        }

        /* Enhanced image styling */
        .stImage {
            width: 100 !important;
            max-width: 1200px !important;
            margin: 0 auto;
        }

        .stImage img {
            width: 100 !important;
            height: auto !important;
            border-radius: 8px;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        }

        .stImage:hover img {
            transform: scale(1.02);
            transition: transform 0.3s ease;
        }

        /* Image caption styling */
        .stImage > div:last-child {
            text-align: center;
            font-size: 1rem;
            color: #666;
            margin-top: 8px;
        }

        /* Image container spacing */
        .element-container:has(.stImage) {
            margin: 2rem auto;
            padding: 1rem 0;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# ✅ Function to create a title from prompt
def generate_title_from_prompt(prompt, max_length=30):
    """Generate a title from the user prompt."""
    clean_prompt = ' '.join(prompt.split())
    if len(clean_prompt) > max_length:
        title = clean_prompt[:max_length] + "..."
    else:
        title = clean_prompt
    return title

# ✅ Sidebar UI (New Chat, Search, Language Selector)
st.sidebar.title("Settings")

# New Chat Button
if st.sidebar.button("➕ New Chat", key="new_chat"):
    try:
        new_chat_id = create_new_chat(title="New Chat")
        if new_chat_id:
            st.session_state.current_chat_id = new_chat_id
            st.session_state.messages = []
            st.rerun()
    except Exception as e:
        st.sidebar.error(f"Could not create new chat: {str(e)}")

# Search functionality
st.sidebar.markdown("## Search Conversations")
search_query = st.sidebar.text_input("Search by topic:", key="search_input", value=st.session_state.search_query)

if search_query != st.session_state.search_query:
    st.session_state.search_query = search_query
    st.rerun()

# Display Chat History in Sidebar
st.sidebar.markdown("## Chat History")
filtered_chats = []

try:
    if st.session_state.search_query:
        filtered_chats = search_chats(st.session_state.search_query)
        if not filtered_chats:
            st.sidebar.info(f"No results found for '{st.session_state.search_query}'")
    else:
        filtered_chats = get_chat_list()
except Exception as e:
    st.sidebar.error(f"Could not load chat history: {str(e)}")

# Group chats by date
today_chats = []
yesterday_chats = []
this_week_chats = []
this_month_chats = []
older_chats = []

if filtered_chats:
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    this_week = today - timedelta(days=7)
    this_month = today.replace(day=1)

    for chat in filtered_chats:
        if "updated_at" in chat and hasattr(chat["updated_at"], "date"):
            chat_date = chat["updated_at"].date()
            if chat_date == today:
                today_chats.append(chat)
            elif chat_date == yesterday:
                yesterday_chats.append(chat)
            elif chat_date > this_week:
                this_week_chats.append(chat)
            elif chat_date >= this_month:
                this_month_chats.append(chat)
            else:
                older_chats.append(chat)
        else:
            today_chats.append(chat)

# Function to display chat items in sidebar
def render_chat_list(title, chats):
    if chats:
        st.sidebar.markdown(f"### {title}")
        for chat in chats:
            chat_id = str(chat["_id"])
            chat_title = chat.get("title", "Untitled Chat")
            
            col1, col2 = st.sidebar.columns([4, 1])
            
            if col1.button(f"{chat_title}", key=f"chat_{chat_id}"):
                chat_data = get_chat_by_id(chat_id)
                if chat_data:
                    st.session_state.current_chat_id = chat_id
                    st.session_state.messages = chat_data.get("messages", [])
                    st.rerun()
            
            if col2.button("🗑️", key=f"delete_{chat_id}"):
                if delete_chat(chat_id):
                    if st.session_state.current_chat_id == chat_id:
                        st.session_state.current_chat_id = None
                        st.session_state.messages = []
                    st.rerun()

# Display grouped chats in sidebar
render_chat_list("Today", today_chats)
render_chat_list("Yesterday", yesterday_chats)
render_chat_list("This Week", this_week_chats)
render_chat_list("This Month", this_month_chats)
render_chat_list("Older", older_chats)

# Language selection
st.sidebar.markdown("## Language")
selected_language = st.sidebar.radio("Choose Language:", ["English", "Japanese"])
st.session_state.language = selected_language

# ✅ Display Chat History in Main Area
def display_chat_history():
    """Displays past messages with feedback buttons."""
    for idx, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            if message["role"] == "assistant":
                # Add feedback buttons for assistant messages
                col1, col2, col3 = st.columns([1, 6, 1])
                with col1:
                    if st.button("👍", key=f"history_thumbs_up_{idx}"):
                        pass  # Handle thumbs-up if needed
                with col3:
                    if st.button("👎", key=f"history_thumbs_down_{idx}"):
                        # Get corresponding user message
                        user_idx = idx - 1 if idx > 0 else None
                        if user_idx is not None and user_idx < len(st.session_state.messages):
                            user_msg = st.session_state.messages[user_idx]["content"]
                            # Set regeneration parameters
                            st.session_state.needs_regeneration = True
                            st.session_state.regeneration_prompt = user_msg
                            st.session_state.regeneration_index = idx
                            # Remove the assistant message
                            st.session_state.messages.pop(idx)
                            # Update the database to remove the old assistant message
                            if st.session_state.current_chat_id:
                                try:
                                    db = get_db()
                                    chat_collection = db["chats"]
                                    chat_collection.update_one(
                                        {"_id": st.session_state.current_chat_id},
                                        {"$set": {"messages": st.session_state.messages}}
                                    )
                                except Exception as e:
                                    st.error(f"Error updating chat history: {str(e)}")
                            st.rerun()

# ✅ Handle User Input and Display Steps + Images
def handle_user_input(prompt, regenerate=False, message_index=None):
    """Process user input and display text response with feedback."""
    if not regenerate:
        if not st.session_state.current_chat_id:
            title = generate_title_from_prompt(prompt)
            new_chat_id = create_new_chat(title=title)
            if new_chat_id is None:
                st.error("Failed to create new chat.")
                return
            st.session_state.current_chat_id = new_chat_id

        # Append user message only if it doesn't already exist
        if not any(msg["role"] == "user" and msg["content"] == prompt for msg in st.session_state.messages):
            st.session_state.messages.append({"role": "user", "content": prompt})
            # Display user message immediately
            with st.chat_message("user"):
                st.markdown(prompt)
            # Save user message to database
            if st.session_state.current_chat_id:
                try:
                    save_message(st.session_state.current_chat_id, {"role": "user", "content": prompt})
                except Exception as e:
                    st.error(f"Error saving user message: {str(e)}")
    
    # Generate and display assistant response
    with st.chat_message("assistant"):
        try:
            with st.spinner("Thinking..." if not regenerate else "Regenerating response..."):
                response_data = generate_response(prompt, st.session_state.language)
                content = response_data["response"]
                
                # Prepare message data
                message_data = {
                    "role": "assistant",
                    "content": content
                }
                
                # Append or update message in session state
                if not regenerate or message_index is None:
                    st.session_state.messages.append(message_data)
                else:
                    # Ensure index is valid and replace the old assistant message
                    if 0 <= message_index < len(st.session_state.messages):
                        st.session_state.messages[message_index] = message_data
                    else:
                        st.session_state.messages.append(message_data)
                
                # Save assistant message to database
                if st.session_state.current_chat_id:
                    try:
                        save_message(st.session_state.current_chat_id, message_data)
                    except Exception as e:
                        st.error(f"Error saving assistant message: {str(e)}")
                
                # Display content
                st.markdown(content)
                
                # Increment feedback key to force button refresh
                st.session_state.feedback_key += 1
                
                # Add feedback buttons
                col1, col2, col3 = st.columns([1, 6, 1])
                with col1:
                    if st.button("👍", key=f"thumbs_up_{st.session_state.feedback_key}"):
                        pass  # Handle thumbs-up if needed
                with col3:
                    if st.button("👎", key=f"thumbs_down_{st.session_state.feedback_key}"):
                        # Find new index of this assistant message
                        new_index = len(st.session_state.messages) - 1
                        # Set regeneration parameters
                        st.session_state.needs_regeneration = True
                        st.session_state.regeneration_prompt = prompt
                        st.session_state.regeneration_index = new_index
                        # Remove the assistant message
                        st.session_state.messages.pop(new_index)
                        # Update the database to remove the old assistant message
                        if st.session_state.current_chat_id:
                            try:
                                db = get_db()
                                chat_collection = db["chats"]
                                chat_collection.update_one(
                                    {"_id": st.session_state.current_chat_id},
                                    {"$set": {"messages": st.session_state.messages}}
                                )
                            except Exception as e:
                                st.error(f"Error updating chat history: {str(e)}")
                        st.rerun()
                    
        except Exception as e:
            st.error(f"Error processing response: {str(e)}")

# ✅ Streamlit UI
st.title("Archibus AI")
st.markdown("Welcome to Archibus AI")

# Display chat history immediately
display_chat_history()

# Handle regeneration
if st.session_state.needs_regeneration and st.session_state.regeneration_prompt:
    handle_user_input(
        st.session_state.regeneration_prompt,
        regenerate=True,
        message_index=st.session_state.regeneration_index
    )
    st.session_state.needs_regeneration = False
    st.session_state.regeneration_prompt = None
    st.session_state.regeneration_index = None

# Handle new user input
if prompt := st.chat_input("Ask me anything..."):
    handle_user_input(prompt)
    st.rerun()  # Force a rerun to ensure chat history updates immediately