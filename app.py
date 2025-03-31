import streamlit as st
from chatbot.response_generator import generate_response
from chatbot.query_handler import find_relevant_images
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
from bson.objectid import ObjectId
import traceback
import html

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

if "pending_chat_id" not in st.session_state:
    st.session_state.pending_chat_id = None

# ✅ Custom Navbar
# Update the CSS styling section with enhanced UI for history
st.markdown(
    """
    <style>
        /* Global Styling */
        body {
            font-family: 'Arial', sans-serif;
        }

        /* ✅ Navbar Styling */
        .navbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 5px 5px;
            background-color: #262730;
            color: white;
            border-bottom: 2px solid #333;
            font-size: 18px;
            font-weight: bold;
        }

        /* ✅ Sidebar Styling */
        .sidebar-content {
            padding: 10px 15px;
            background-color: #f9f9f9;
            border-right: 2px solid #ddd;
        }

        /* ✅ Chat History Styling */
        .chat-item {
            padding: 5px !important;
            margin: 9px 0 !important;
            border-radius: 4px;
            cursor: pointer;
            background-color: #f4f4f4;
            transition: background-color 0.2s;
            height: 36px !important;
            overflow: hidden;
        }
        
        /* Fixed height for chat title button */
        .stButton button {
            height: 36px !important;
            min-height: 36px !important;
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
        }

        .chat-item:hover {
            background-color: #eaeaea;
        }

        .active-chat button {
            background-color: #ff4d4d !important; 
            color: white !important;
            font-weight: bold !important;
        }

        /* ✅ Delete Button */
        .delete-btn {
            
            width: 24px !important;
            height: 24px !important;
            min-height: 0 !important;
            line-height: 1 !important;
            font-size: 10px !important;
            color: #888 !important;
            background-color: transparent !important;
        }

        .delete-btn:hover {
            color: #ff4d4d !important;
            background-color: rgba(255, 77, 77, 0.1) !important;
        }
        
        /* Chat section header styling */
        .chat-section-header {
            font-size: 20px !important;
            color: #000000 !important; /* Changed from white to black */
            margin-top: 8px !important;
            margin-bottom: 4px !important;
            padding-bottom: 2px !important;
        }
        
        /* Reduce spacing in sidebar */
        .block-container {
            padding-top: 1rem !important;
            padding-bottom: 1rem !important;
        }
        
        /* Compact sidebar sections */
        .sidebar .stMarkdown h2 {
            margin-top: 0.5rem !important;
            margin-bottom: 0.3rem !important;
            font-size: 1.1rem !important;
        }

    </style>
    """,
    unsafe_allow_html=True
)

# ✅ Function to create a title from prompt
def generate_title_from_prompt(prompt, max_length=20):
    """Generate a title from the user prompt."""
    # Remove special characters and normalize whitespace
    clean_prompt = ' '.join(prompt.split())
    
    # Limit length
    if len(clean_prompt) > max_length:
        title = clean_prompt[:max_length] + "..."
    else:
        title = clean_prompt
        
    return title

# Function to load chat by ID - separated for clarity
def load_chat_by_id(chat_id):
    """Load a chat by its ID and set it as the current chat"""
    try:
        # Get chat data - using ObjectId conversion
        try:
            obj_id = ObjectId(chat_id)
            chat_data = get_chat_by_id(obj_id)
        except:
            chat_data = get_chat_by_id(chat_id)
        
        if chat_data is not None:
            # Set as current chat
            st.session_state.current_chat_id = chat_id
            
            # Load messages
            if "messages" in chat_data and isinstance(chat_data["messages"], list):
                st.session_state.messages = chat_data["messages"]
            else:
                st.session_state.messages = []
            
            return True
        else:
            st.sidebar.error(f"Could not find chat with ID: {chat_id}")
    except Exception as e:
        st.sidebar.error(f"Error loading chat: {str(e)}")
        traceback.print_exc()
    
    return False

# ✅ Sidebar UI (New Chat, Search, Language Selector)
st.sidebar.title("Archibus AI")

# New Chat Button
if st.sidebar.button("➕ New Chat", key="new_chat"):
    # For new chat, just clear the messages and reset current_chat_id
    # Don't create a database entry until first message
    st.session_state.messages = []
    st.session_state.current_chat_id = None
    st.rerun()
        
# Search functionality
search_query = st.sidebar.text_input("🔍 Search conversations", key="search_input", value=st.session_state.search_query)

if search_query != st.session_state.search_query:
    st.session_state.search_query = search_query
    st.rerun()
    
# Display Chat History
st.sidebar.markdown("## Chat History")

# In the section where you display chat history
filtered_chats = []

try:
    if st.session_state.search_query:
        # Search and display results directly
        filtered_chats = search_chats(st.session_state.search_query)
        if filtered_chats is None:
            filtered_chats = []
        if len(filtered_chats) == 0:
            st.sidebar.info(f"No results found for '{st.session_state.search_query}'")
        else:
            # Sort by updated_at date in descending order
            filtered_chats = sorted(filtered_chats, 
                                key=lambda x: x.get("updated_at", datetime.min), 
                                reverse=True)
    else:
        # Display all chats when not searching
        filtered_chats = get_chat_list()
        if filtered_chats is None:
            filtered_chats = []
        else:
            # Sort by updated_at date in descending order
            filtered_chats = sorted(filtered_chats, 
                               key=lambda x: x.get("updated_at", datetime.min), 
                               reverse=True)
except Exception as e:
    st.sidebar.error(f"Could not load chat history. Database connection issue: {str(e)}")
    filtered_chats = []
    
# Group chats by date - only if we have chats
today_chats = []
yesterday_chats = []
this_week_chats = []
this_month_chats = []
older_chats = []

if filtered_chats and len(filtered_chats) > 0:
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    this_week = today - timedelta(days=7)
    this_month = today.replace(day=1)

    # Sort the filtered chats by updated_at in descending order first
    try:
        filtered_chats = sorted(filtered_chats, 
                               key=lambda x: x.get("updated_at", datetime.min), 
                               reverse=True)
    except Exception as e:
        st.sidebar.warning(f"Error sorting chats: {str(e)}")

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

# ✅ Fixed render_chat_list function with direct chat loading
# ✅ Enhanced render_chat_list function with better UI
def render_chat_list(title, chats):
    if chats and len(chats) > 0:
        # Section header with better styling
        st.sidebar.markdown(f"<div class='chat-section-header'>{title}</div>", unsafe_allow_html=True)
        
        # Create a container for this section
        with st.sidebar.container():
            for chat in chats:
                chat_id = str(chat["_id"])
                chat_title = chat.get("title", "Untitled Chat")
                
                # Check if this is the active chat
                is_active = (st.session_state.current_chat_id == chat_id)
                
                # Create a chat container with conditional active class
                chat_container_class = "chat-item active-chat" if is_active else "chat-item"
                
                # Create a horizontal layout with columns
                col1, col2 = st.sidebar.columns([8, 1])
                
                # Chat button with styled title
                with col1:
                    if st.button(chat_title, key=f"chat_{chat_id}", use_container_width=True, 
                              help="Click to open this chat", 
                              type="secondary" if is_active else "primary"):
                        # Set pending chat ID to avoid issues with Streamlit reruns
                        st.session_state.pending_chat_id = chat_id
                        st.rerun()
                
                # Delete button in the second column - smaller and more stylized
                with col2:
                    if st.button("🗑️", key=f"delete_{chat_id}", help="Delete this chat", 
                              use_container_width=True, type="secondary"):
                        if delete_chat(chat_id):
                            if st.session_state.current_chat_id == chat_id:
                                st.session_state.current_chat_id = None
                                st.session_state.messages = []
                            st.rerun()

# Handle pending chat ID (if any)
if st.session_state.pending_chat_id is not None:
    chat_id = st.session_state.pending_chat_id
    st.session_state.pending_chat_id = None  # Clear pending ID
    load_chat_by_id(chat_id)

# Display grouped chats with updated color
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
    """Displays past messages and retrieved images with proper section-image pairing."""
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant":
                # Get content and images
                content = message["content"]
                image_urls = message.get("image_urls", [])
                
                # Split content into sections
                sections = [s.strip() for s in content.split("\n\n") if s.strip()]
                
                # Display sections with their corresponding images
                for idx, section in enumerate(sections):
                    st.markdown(section)
                    # Only display image if it exists for this section
                    if idx < len(image_urls) and image_urls[idx]:
                        st.image(image_urls[idx], caption=f"Related Image {idx+1}")
            else:
                st.markdown(message["content"])

# ✅ Handle User Input and Display Steps + Images
def handle_user_input(prompt):
    """Processes user input and retrieves AI response & multiple images in order."""
    # Create user message dict first
    user_message = {"role": "user", "content": prompt}
    
    # Add user message to session state
    st.session_state.messages.append(user_message)
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate and display assistant response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            # If this is the first message, create a new chat with title from prompt
            if st.session_state.current_chat_id is None:
                title = generate_title_from_prompt(prompt)
                try:
                    # Create new chat with title immediately
                    new_chat_id = create_new_chat(title=title)
                    if new_chat_id is not None:
                        st.session_state.current_chat_id = new_chat_id
                        # Force sidebar refresh to show new chat
                        st.sidebar.success(f"Created new chat: {title}")
                    else:
                        st.error("Failed to create new chat. Database connection issue.")
                        return
                except Exception as e:
                    st.error(f"Failed to create new chat: {str(e)}")
                    return
                
                # Save first message after creating chat
                if st.session_state.current_chat_id is not None:
                    saved = save_message(st.session_state.current_chat_id, user_message)
                    if not saved:
                        st.error("Failed to save message to database.")
            else:
                # For existing chats, just save the message
                saved = save_message(st.session_state.current_chat_id, user_message)
                if not saved:
                    st.error("Failed to save message to database.")

            # Get response and images
            response_text = generate_response(prompt, st.session_state.language)
            image_urls = find_relevant_images(prompt, top_k=5)
            image_urls = [url for url in image_urls if url]  # Remove empty URLs

            # Split response into sections
            sections = [s.strip() for s in response_text.split("\n\n") if s.strip()]

            # Store the message
            response_message = {
                "role": "assistant",
                "content": response_text,
                "image_urls": image_urls
            }
            st.session_state.messages.append(response_message)

            # Display current response with images
            for idx, section in enumerate(sections):
                st.markdown(section)
                if idx < len(image_urls) and image_urls[idx]:
                    st.image(image_urls[idx], caption=f"Related Image {idx+1}")

            # Save assistant response to database
            if st.session_state.current_chat_id is not None:
                saved = save_message(st.session_state.current_chat_id, response_message)
                if not saved:
                    st.error("Failed to save response to database.")
            
            # Force rerun to update sidebar with new chat
            st.rerun()
            
# ✅ Streamlit UI
st.title("Archibus")
st.markdown("Welcome to Archibus AI")

display_chat_history()

if prompt := st.chat_input("Ask me anything..."):
    handle_user_input(prompt)