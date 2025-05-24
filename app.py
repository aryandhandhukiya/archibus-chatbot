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
import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import os

# Load precomputed embeddings and index
# EMBEDDINGS_PATH = "D:\\ArchiBusV2\\archibus-chatbot\\pdf-embeddings\\text_embeddings.npy"
# INDEX_PATH = "D:\\ArchiBusV2\\archibus-chatbot\\pdf-embeddings\\text_index.faiss"
# METADATA_PATH = "D:\\ArchiBusV2\\archibus-chatbot\\pdf-embeddings\\metadata.json"

EMBEDDINGS_PATH = "pdf-embeddings/text_embeddings.npy"
INDEX_PATH = "pdf-embeddings/text_index.faiss"
METADATA_PATH = "pdf-embeddings/metadata.json"

# Load the precomputed data
text_embeddings = np.load(EMBEDDINGS_PATH)
text_index = faiss.read_index(INDEX_PATH)
with open(METADATA_PATH, "r") as f:
    metadata = json.load(f)
texts = metadata["texts"]
dataset = metadata["dataset"]

# Initialize text embedder for embedding step text
text_embedder = SentenceTransformer('all-MiniLM-L6-v2')

# Function to dynamically split the text response into steps, intro, and conclusion
def split_response_into_steps(text_response):
    numbered_pattern = r'(\d+\.\s|\d+\)\s)'
    transitional_phrases = [
        r'First(?:,|\b)',
        r'Next(?:,|\b)',
        r'After that(?:,|\b)',
        r'Now(?:,|\b)',
        r'Finally(?:,|\b)',
        r'Step\s+\d+(?:,|\b)'
    ]
    transitional_pattern = '|'.join(transitional_phrases)
    step_pattern = f'({numbered_pattern}|{transitional_pattern})'
    conclusion_pattern = r'(Conclusion:|In conclusion,).*$'

    # Extract conclusion
    conclusion_match = re.search(conclusion_pattern, text_response, re.IGNORECASE | re.DOTALL)
    conclusion_text = conclusion_match.group(0).strip() if conclusion_match else ""
    if conclusion_match:
        text_response = text_response[:conclusion_match.start()].strip()

    # Find all matches of step markers
    matches = list(re.finditer(step_pattern, text_response, re.IGNORECASE))
    
    if not matches:
        return text_response.strip(), [("Full Response", text_response.strip())], conclusion_text

    # Extract the introductory text (before the first step)
    intro_text = text_response[:matches[0].start()].strip()

    # Split the response into steps based on matches
    steps = []
    step_dict = {}  # To track steps by name and merge duplicates
    for i, match in enumerate(matches):
        start_pos = match.start()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(text_response)
        step_text = text_response[start_pos:end_pos].strip()
        step_name = match.group().strip()
        if step_name.endswith(","):
            step_name = step_name[:-1]

        # Normalize step name for deduplication (case-insensitive)
        step_name_key = step_name.lower()
        if step_name_key in step_dict:
            # Merge the step text with the existing step
            step_dict[step_name_key]["text"] += "\n" + step_text
        else:
            step_dict[step_name_key] = {"name": step_name, "text": step_text}

    # Convert the dictionary to a list of tuples, ensuring sequential numbering
    step_counter = 1
    for step_key, step_data in sorted(step_dict.items(), key=lambda x: matches[list(step_dict.keys()).index(x[0])].start()):
        step_name = step_data["name"]
        # If the step name is a number (e.g., "1."), use it; otherwise, use the counter
        if re.match(r'^\d+\.\s', step_name):
            steps.append((step_name, step_data["text"]))
        else:
            steps.append((f"{step_counter}.", step_data["text"]))
            step_counter += 1
    
    return intro_text, steps, conclusion_text

# Function to resize image to a fixed width while maintaining aspect ratio
def resize_image(image, target_width=600):
    original_width, original_height = image.size
    aspect_ratio = original_height / original_width
    target_height = int(target_width * aspect_ratio)
    return image.resize((target_width, target_height), Image.Resampling.LANCZOS)

# Function to find images based on step text, default to 1 image per step
def find_images_for_step(step_text, used_images, k=3, max_images=1):
    step_embedding = text_embedder.encode([step_text], convert_to_numpy=True)
    D, I = text_index.search(step_embedding, k=k)
    
    matching_images = []
    for idx in I[0]:
        page_data = dataset[idx]
        page_number = page_data["page_number"]
        images = page_data["images"]
        
        for img_path in images:
            img_filename = os.path.basename(img_path)
            try:
                img_number = int(img_filename.split("_")[-1].replace(".png", ""))
                image_key = (page_number, img_number)
                if image_key not in used_images:
                    used_images.add(image_key)
                    matching_images.append((page_number, img_number, img_path))
                    if len(matching_images) >= max_images:
                        break
            except (IndexError, ValueError) as e:
                st.error(f"Error parsing image path {img_path}: {e}")
                continue
        if len(matching_images) >= max_images:
            break
    
    # Fallback: If no images are found, search again with a broader query
    if len(matching_images) < max_images:
        simplified_text = " ".join(step_text.split()[:5])  # Use first 5 words
        step_embedding = text_embedder.encode([simplified_text], convert_to_numpy=True)
        D, I = text_index.search(step_embedding, k=k)
        for idx in I[0]:
            page_data = dataset[idx]
            page_number = page_data["page_number"]
            images = page_data["images"]
            for img_path in images:
                img_filename = os.path.basename(img_path)
                try:
                    img_number = int(img_filename.split("_")[-1].replace(".png", ""))
                    image_key = (page_number, img_number)
                    if image_key not in used_images:
                        used_images.add(image_key)
                        matching_images.append((page_number, img_number, img_path))
                        if len(matching_images) >= max_images:
                            break
                except (IndexError, ValueError) as e:
                    st.error(f"Error parsing image path {img_path}: {e}")
                    continue
            if len(matching_images) >= max_images:
                break
    
    return matching_images[:max_images]

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

# Custom Navbar and Styling
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

# Display Chat History in Main Area
def display_chat_history():
    for idx, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            content = message.get("content", "")
            if message["role"] == "assistant" and "steps" in message:
                # Extract components
                intro_text = message.get("intro_text", "")
                steps = message.get("steps", [])
                conclusion_text = message.get("conclusion_text", "")
                
                # Display introductory text
                if intro_text:
                    st.markdown(intro_text)
                
                # Display steps with images
                for step_name, step_text in steps:
                    with st.container():
                        st.markdown(f"**Step: {step_name}**")
                        st.markdown(step_text)
                        if step_name in message.get("step_images", {}) and message["step_images"][step_name]:
                            for page_num, img_num, img_path in message["step_images"][step_name]:
                                try:
                                    image = Image.open(img_path)
                                    resized_image = resize_image(image, target_width=600)
                                    caption = f"Page {page_num}, Image {img_num}"
                                    st.image(resized_image, caption=caption, use_container_width=True)
                                except Exception as e:
                                    st.error(f"Error loading image {img_path}: {str(e)}")
                
                # Display conclusion (no images)
                if conclusion_text:
                    st.markdown("### Conclusion")
                    st.markdown(conclusion_text)
            else:
                st.markdown(content)
            
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

# Handle User Input and Display Steps + Images
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
                response_data = generate_response(prompt, st.session_state.language)
                content = response_data["response"]
                
                # Split the response into introductory text, steps, and conclusion
                intro_text, steps, conclusion_text = split_response_into_steps(content)
                
                # Find images for each step, default to 1 image
                step_images = {}
                used_images = set()
                for step_name, step_text in steps:
                    matching_images = find_images_for_step(step_text, used_images, k=3, max_images=1)
                    step_images[step_name] = matching_images
                
                # Prepare message data with steps and images
                message_data = {
                    "role": "assistant",
                    "content": content,
                    "intro_text": intro_text,
                    "steps": steps,
                    "conclusion_text": conclusion_text,
                    "step_images": step_images
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
                if intro_text:
                    st.markdown(intro_text)
                
                # Display steps with images
                for step_name, step_text in steps:
                    with st.container():
                        st.markdown(f"**Step: {step_name}**")
                        st.markdown(step_text)
                        if step_name in step_images and step_images[step_name]:
                            for page_num, img_num, img_path in step_images[step_name]:
                                try:
                                    image = Image.open(img_path)
                                    resized_image = resize_image(image, target_width=600)
                                    caption = f"Page {page_num}, Image {img_num}"
                                    st.image(resized_image, caption=caption, use_container_width=True)
                                except Exception as e:
                                    st.error(f"Error loading image {img_path}: {str(e)}")
                
                # Display conclusion (no images)
                if conclusion_text:
                    st.markdown("### Conclusion")
                    st.markdown(conclusion_text)
                
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