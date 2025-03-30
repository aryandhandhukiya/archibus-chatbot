import os
import sys
import streamlit as st
from datetime import datetime, timedelta
from chatbot.response_generator import generate_response
from chatbot.query_handler import find_relevant_images
from mongodb_utils import (
    create_new_chat, 
    save_message, 
    get_chat_list, 
    get_chat_by_id,
    search_chats,
    delete_chat
)

# Page configuration
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

# ✅ Custom CSS
st.markdown(
    """
    <style>
        /* ✅ Hide "Manage App" button */
        .stDeployButton, 
        .viewerBadge_container__1QSob,
        #manage-app-button {
            display: none !important;
        }

        /* ✅ Hide "Hosted with Streamlit" message & GitHub logo from footer */
        footer, .viewerBadge_link__1S137 {
            display: none !important;
            visibility: hidden !important;
        }
        
        /* ✅ Hide any additional elements in the footer */
        footer .st-emotion-cache, footer div {
            display: none !important;
        }

        /* ✅ Keep the three-dot (⋮) menu visible */
        button[data-testid="stAppViewerMenuButton"] {
            display: inline-flex !important;
            visibility: visible !important;
        }

        /* ✅ Hide Streamlit Main Menu (GitHub logo) */
        #MainMenu {
            display: none !important;
        }

        /* ✅ Hide unnecessary toolbar elements */
        div[data-testid="stToolbar"] {
            display: none !important;
        }

        /* ✅ Hide unwanted toolbar buttons */
        button[title="View fullscreen"],
        button[title="Download"],
        button[title="Share"],
        button[title="View source"],
        button[title="Edit source"],
        button[title="Star"] {
            display: none !important;
        }

        /* ✅ Style adjustments for navbar */
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
    </style>
    """,
    unsafe_allow_html=True
)

# ✅ Sidebar UI
st.sidebar.title("Archibus Chat")

# New Chat Button
# In the New Chat Button handler around line 123:
if st.sidebar.button("➕ New Chat", key="new_chat"):
    try:
        # Create new chat in MongoDB
        new_chat_id = create_new_chat()
        if new_chat_id:
            st.session_state.current_chat_id = new_chat_id
            st.session_state.messages = []
            st.rerun()
    except Exception as e:
        st.sidebar.error("Could not create new chat. Database connection issue.")

# Search functionality
st.sidebar.markdown("## Search Conversations")
search_query = st.sidebar.text_input("Search by topic:", key="search_input", value=st.session_state.search_query)

if search_query != st.session_state.search_query:
    st.session_state.search_query = search_query
    st.rerun()  # Changed from st.experimental_rerun()

# Display Chat History
st.sidebar.markdown("## Chat History")

# Around line 143, modify the chat history display:
filtered_chats = []

try:
    chat_list = get_chat_list()
    if chat_list:  # If we got a valid list
        filtered_chats = chat_list
        
        if st.session_state.search_query:
            # Display search results
            search_results = search_chats(st.session_state.search_query)
            if search_results:
                filtered_chats = search_results
            else:
                st.sidebar.info(f"No results found for '{st.session_state.search_query}'")
                filtered_chats = []
except Exception as e:
    st.sidebar.error(f"Could not load chat history. Database connection issue.")

# Group chats by date - only if we have chats
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
        # Make sure we have updated_at field with proper date
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
            # If no date or invalid date format, put in today's chats
            today_chats.append(chat)

# Function to display chat items
def render_chat_list(title, chats):
    if chats:
        st.sidebar.markdown(f"### {title}")
        for chat in chats:
            chat_id = str(chat["_id"])
            chat_title = chat.get("title", "Untitled Chat")
            
            # Create a horizontal layout with columns
            col1, col2 = st.sidebar.columns([4, 1])
            
            # Chat button in the first (wider) column
            if col1.button(f"{chat_title}", key=f"chat_{chat_id}"):
                chat_data = get_chat_by_id(chat_id)
                if chat_data:
                    st.session_state.current_chat_id = chat_id
                    st.session_state.messages = chat_data.get("messages", [])
                    st.rerun()
            
            # Delete button in the second (narrower) column
            if col2.button("🗑️", key=f"delete_{chat_id}"):
                if delete_chat(chat_id):
                    # If the deleted chat was the current chat, clear the messages
                    if st.session_state.current_chat_id == chat_id:
                        st.session_state.current_chat_id = None
                        st.session_state.messages = []
                    st.rerun()

# Display grouped chats
render_chat_list("Today", today_chats)
render_chat_list("Yesterday", yesterday_chats)
render_chat_list("This Week", this_week_chats)
render_chat_list("This Month", this_month_chats)
render_chat_list("Older", older_chats)

# ✅ Language selection in sidebar
st.sidebar.markdown("## Language")
selected_language = st.sidebar.radio("Choose Language:", ["English", "Japanese"])
st.session_state.language = selected_language

# ✅ Display Chat History
def display_chat_history():
    """Displays past messages and retrieved images."""
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "image_urls" in message:
                for img_url in message["image_urls"]:
                    st.image(img_url, caption="Relevant Image")

# ✅ Handle User Input and Display Steps + Images
def handle_user_input(prompt):
    """Processes user input and retrieves AI response & multiple images in order."""
    
    if not prompt.strip():  # ✅ Prevent empty messages from being processed
        return  

    # Track if this is a new chat being created
    new_chat_created = False

    # ✅ Create a new chat IMMEDIATELY when user sends first message
    if not st.session_state.current_chat_id:
        # Use first part of the user's message as the chat title
        chat_title = prompt[:40] + ("..." if len(prompt) > 40 else "")
        new_chat_id = create_new_chat(title=chat_title)
        if new_chat_id:
            st.session_state.current_chat_id = new_chat_id
            new_chat_created = True
    
    # ✅ Add user message to session state
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # ✅ Save user message to MongoDB if a chat exists
    if st.session_state.current_chat_id:
        save_message(st.session_state.current_chat_id, "user", prompt)

    # Continue with the rest of the function (display message, get AI response, etc.)
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            # ✅ Generate response
            response_text = generate_response(prompt, st.session_state.language)

            # ✅ Fetch images
            image_urls = find_relevant_images(prompt, top_k=5)
            image_urls = [url for url in image_urls if url]  # ✅ Remove blank images  

            response_message = {"role": "assistant", "content": response_text}
            if image_urls:
                response_message["image_urls"] = list(dict.fromkeys(image_urls))  # Remove duplicates
            
            # ✅ Add response to session state
            st.session_state.messages.append(response_message)
            
            # ✅ Save response to MongoDB
            if st.session_state.current_chat_id:
                save_message(
                    st.session_state.current_chat_id,
                    "assistant", 
                    response_text, 
                    response_message.get("image_urls")
                )

            # ✅ Display formatted response
            st.markdown("### AI Response")
            st.markdown(response_text)

            # ✅ Step-wise Display with Grouped Sections
            st.markdown("### Key Sections")

            sections = response_text.split("\n\n")  # Split response into sections

            for idx, section in enumerate(sections):
                st.markdown(f"#### {section}")

                if idx < len(image_urls):
                    st.image(image_urls[idx], caption=f"Relevant Image {idx+1}")
    
    # Force a refresh AFTER AI has responded if this is a new chat
    if new_chat_created:
        st.rerun()


# ✅ Streamlit UI
st.title("Archibus AI")
st.markdown("Welcome to Archibus AI")

# If no active chat, create one
# if not st.session_state.current_chat_id and not st.session_state.messages:
#     new_chat_id = create_new_chat()
#     if new_chat_id:
#         st.session_state.current_chat_id = new_chat_id

display_chat_history()

# Add a message to show when no MongoDB connection
if not st.session_state.current_chat_id and st.session_state.messages == []:
    st.info("Enter your question below to start a conversation with Archibus AI.")
    st.info("Note: Chat history functionality may be limited if database connection is unavailable.")

if prompt := st.chat_input("Ask me anything..."):
    handle_user_input(prompt)