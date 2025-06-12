import streamlit as st
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
from io import BytesIO
from PIL import Image
import requests
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI backend URL
BACKEND_URL = "https://97bf-103-20-65-202.ngrok-free.app"

# Function to check if the backend is running
def check_backend_health():
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=5)
        response.raise_for_status()
        return response.json().get("status") == "ok"
    except requests.exceptions.RequestException as e:
        logger.error(f"Backend health check failed: {str(e)}")
        return False

# Ensure backend is running
if not check_backend_health():
    st.error("FastAPI backend is not running. Please start the server at http://localhost:8000.")
    st.stop()

# Enhanced function to standardize image size with padding (maintains aspect ratio)
def standardize_image_size(image, target_width=600, target_height=400, fill_color=(255, 255, 255)):
    """
    Standardize image size by resizing and padding to exact dimensions
    """
    # Convert to RGB if necessary (handles RGBA, grayscale, etc.)
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    # Calculate scaling factor to fit image within target dimensions
    original_width, original_height = image.size
    scale_width = target_width / original_width
    scale_height = target_height / original_height
    scale = min(scale_width, scale_height)  # Use smaller scale to fit entirely
    
    # Resize image maintaining aspect ratio
    new_width = int(original_width * scale)
    new_height = int(original_height * scale)
    image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # Create new image with target dimensions and fill color
    standardized_image = Image.new('RGB', (target_width, target_height), fill_color)
    
    # Calculate position to center the resized image
    x_offset = (target_width - new_width) // 2
    y_offset = (target_height - new_height) // 2
    
    # Paste the resized image onto the standardized canvas
    standardized_image.paste(image, (x_offset, y_offset))
    
    return standardized_image

# Function to load an image from an S3 URL with silent error handling
def load_image_from_url(url):
    try:
        # Verify that the URL is a string and starts with http/https
        if not isinstance(url, str) or not url.startswith(('http://', 'https://')):
            return None

        # Fetch the image from the URL
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()  # Raise an error for bad status codes (e.g., 403, 404)

        # Load the image data into a BytesIO object
        image_data = BytesIO(response.content)

        # Open the image with PIL
        image = Image.open(image_data)
        
        # Verify that the image is valid by accessing its size
        image.size  # This will raise an error if the image is corrupt
        
        return image

    except Exception:
        # Silently return None on any error
        return None

st.set_page_config(page_title="Archibus AI", layout="wide")

# Ensure Session State Variables Exist
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

# Enhanced Custom Navbar and Styling with improved image consistency
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

        /* Enhanced image styling for consistent display */
        .stImage {
            display: flex !important;
            justify-content: center !important;
            margin: 1.5rem auto !important;
            max-width: 620px !important;
        }

        .stImage img {
            width: 600px !important;
            height: 400px !important;
            object-fit: contain !important;
            border-radius: 8px !important;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1) !important;
            border: 1px solid #e0e0e0 !important;
            background-color: #f8f9fa !important;
        }

        .stImage:hover img {
            transform: scale(1.02) !important;
            transition: transform 0.3s ease !important;
            box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15) !important;
        }

        /* Image caption styling */
        .stImage > div:last-child {
            text-align: center !important;
            font-size: 0.9rem !important;
            color: #666 !important;
            margin-top: 8px !important;
            font-weight: 500 !important;
        }

        /* Image container spacing */
        .element-container:has(.stImage) {
            margin: 1.5rem auto !important;
            padding: 1rem 0 !important;
            max-width: 620px !important;
        }

        /* Step container styling */
        .step-container {
            margin: 1.5rem 0 !important;
            padding: 1rem !important;
            border-left: 3px solid #007acc !important;
            background-color: #f8f9fa !important;
            border-radius: 0 8px 8px 0 !important;
        }

        /* Ensure consistent spacing for all content */
        .main .block-container {
            padding-top: 2rem !important;
            padding-bottom: 2rem !important;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# Function to create a title from prompt
def generate_title_from_prompt(prompt, max_length=30):
    clean_prompt = ' '.join(prompt.split())
    if len(clean_prompt) > max_length:
        title = clean_prompt[:max_length] + "..."
    else:
        title = clean_prompt
    return title

# Sidebar UI (New Chat, Search, Language Selector)
st.sidebar.title("Settings")

if st.sidebar.button("➕ New Chat", key="new_chat"):
    try:
        new_chat_id = create_new_chat(title="New Chat")
        if new_chat_id:
            st.session_state.current_chat_id = new_chat_id
            st.session_state.messages = []
            st.rerun()
    except Exception as e:
        st.sidebar.error(f"Could not create new chat: {str(e)}")

st.sidebar.markdown("## Search Conversations")
search_query = st.sidebar.text_input("Search by topic:", key="search_input", value=st.session_state.search_query)

if search_query != st.session_state.search_query:
    st.session_state.search_query = search_query
    st.rerun()

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

render_chat_list("Today", today_chats)
render_chat_list("Yesterday", yesterday_chats)
render_chat_list("This Week", this_week_chats)
render_chat_list("This Month", this_month_chats)
render_chat_list("Older", older_chats)

st.sidebar.markdown("## Language")
selected_language = st.sidebar.radio("Choose Language:", ["English", "Japanese"])
st.session_state.language = selected_language

# Display Chat History in Main Area with silent image skipping
def display_chat_history():
    for idx, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            if message["role"] == "user":
                st.markdown(message["content"])
            else:
                # Extract components
                intro_text = message.get("intro_text", "")
                steps = message.get("steps", [])
                conclusion_text = message.get("conclusion_text", "")
                
                # Display introductory text
                if intro_text:
                    st.markdown(intro_text)
                
                # Display steps with silent image skipping
                for step in steps:
                    with st.container():
                        st.markdown(f"**Step: {step['step_name']}**")
                        st.markdown(step["step_text"])
                        if step.get("best_image"):
                            img = step["best_image"]
                            image = load_image_from_url(img["path"])
                            if image:  # Only display if image was loaded successfully
                                standardized_image = standardize_image_size(image, target_width=600, target_height=400)
                                caption = f"Page {img['page']}, Image {img['image']}"
                                st.image(standardized_image, caption=caption, width=600)
                
                # Display conclusion (no images)
                if conclusion_text:
                    st.markdown("### Conclusion")
                    st.markdown(conclusion_text)
            
            if message["role"] == "assistant":
                col1, col2, col3 = st.columns([1, 6, 1])
                with col1:
                    if st.button("👍", key=f"history_thumbs_up_{idx}"):
                        pass
                with col3:
                    if st.button("👎", key=f"history_thumbs_down_{idx}"):
                        user_idx = idx - 1 if idx > 0 else None
                        if user_idx is not None and user_idx < len(st.session_state.messages):
                            user_msg = st.session_state.messages[user_idx]["content"]
                            st.session_state.needs_regeneration = True
                            st.session_state.regeneration_prompt = user_msg
                            st.session_state.regeneration_index = idx
                            st.session_state.messages.pop(idx)
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

# Handle User Input by Sending Request to FastAPI Backend
def handle_user_input(prompt, regenerate=False, message_index=None):
    if not regenerate:
        if not st.session_state.current_chat_id:
            title = generate_title_from_prompt(prompt)
            new_chat_id = create_new_chat(title=title)
            if new_chat_id is None:
                st.error("Failed to create new chat.")
                return
            st.session_state.current_chat_id = new_chat_id

        if not any(msg["role"] == "user" and msg["content"] == prompt for msg in st.session_state.messages):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            if st.session_state.current_chat_id:
                try:
                    save_message(st.session_state.current_chat_id, {"role": "user", "content": prompt})
                except Exception as e:
                    st.error(f"Error saving user message: {str(e)}")
    
    with st.chat_message("assistant"):
        try:
            with st.spinner("Thinking..." if not regenerate else "Regenerating response..."):
                # Send request to FastAPI backend
                payload = {
                    "question": prompt,
                    "language": st.session_state.language
                }
                response = requests.post(f"{BACKEND_URL}/query", json=payload, timeout=30)
                response.raise_for_status()
                response_data = response.json()

                # Prepare message data
                message_data = {
                    "role": "assistant",
                    "intro_text": response_data["intro_text"],
                    "steps": [
                        {
                            "step_name": step["step_name"],
                            "step_text": step["step_text"],
                            "images": step["images"],
                            "best_image": step["best_image"]
                        }
                        for step in response_data["steps"]
                    ],
                    "conclusion_text": response_data["conclusion_text"]
                }
                
                # Append or update message in session state
                if not regenerate or message_index is None:
                    st.session_state.messages.append(message_data)
                else:
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
                
                # Display the introductory text (if any)
                if message_data["intro_text"]:
                    st.markdown(message_data["intro_text"])
                
                # Display steps with silent image skipping
                for step in message_data["steps"]:
                    with st.container():
                        st.markdown(f"**Step: {step['step_name']}**")
                        st.markdown(step["step_text"])
                        if step.get("best_image"):
                            img = step["best_image"]
                            image = load_image_from_url(img["path"])
                            if image:  # Only display if image was loaded successfully
                                standardized_image = standardize_image_size(image, target_width=600, target_height=400)
                                caption = f"Page {img['page']}, Image {img['image']}"
                                st.image(standardized_image, caption=caption, width=600)
                
                # Display conclusion (no images)
                if message_data["conclusion_text"]:
                    st.markdown("### Conclusion")
                    st.markdown(message_data["conclusion_text"])
                
                st.session_state.feedback_key += 1
                col1, col2, col3 = st.columns([1, 6, 1])
                with col1:
                    if st.button("👍", key=f"thumbs_up_{st.session_state.feedback_key}"):
                        pass
                with col3:
                    if st.button("👎", key=f"thumbs_down_{st.session_state.feedback_key}"):
                        new_index = len(st.session_state.messages) - 1
                        st.session_state.needs_regeneration = True
                        st.session_state.regeneration_prompt = prompt
                        st.session_state.regeneration_index = new_index
                        st.session_state.messages.pop(new_index)
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
                    
        except requests.exceptions.RequestException as e:
            st.error(f"Error communicating with backend: {str(e)}")
        except Exception as e:
            st.error(f"Error processing response: {str(e)}")

# Streamlit UI
st.title("Archibus AI")
st.markdown("Welcome to Archibus AI")

display_chat_history()

if st.session_state.needs_regeneration and st.session_state.regeneration_prompt:
    handle_user_input(
        st.session_state.regeneration_prompt,
        regenerate=True,
        message_index=st.session_state.regeneration_index
    )
    st.session_state.needs_regeneration = False
    st.session_state.regeneration_prompt = None
    st.session_state.regeneration_index = None

if prompt := st.chat_input("Ask me anything..."):
    handle_user_input(prompt)
    st.rerun()