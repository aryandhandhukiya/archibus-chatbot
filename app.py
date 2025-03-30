import streamlit as st
from chatbot.response_generator import generate_response
from chatbot.query_handler import find_relevant_images

st.set_page_config(page_title="Archibus AI", layout="wide")

# ✅ Ensure Session State Variables Exist
if "messages" not in st.session_state:
    st.session_state.messages = []

if "language" not in st.session_state:
    st.session_state.language = "Japanese"

# ✅ Custom Navbar
st.markdown(
    """
    <style>
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
    </style>
    <div class="navbar">
        <span class="navbar-title">Archibus AI</span>
    </div>
    """,
    unsafe_allow_html=True
)

# ✅ Sidebar UI (New Chat, Search, Language Selector)
st.sidebar.title("Settings")

if st.sidebar.button("➕ New Chat"):
    st.session_state.messages = []  # Reset chat history

if st.sidebar.button("🔍 Search"):
    st.warning("Search functionality is not yet implemented.")

# ✅ Language selection in sidebar
selected_language = st.sidebar.radio("Choose Language:", ["English", "Japanese"])
st.session_state.language = selected_language  # Update session state with selected language

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
    st.session_state.messages.append({"role": "user", "content": prompt})

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
            
            st.session_state.messages.append(response_message)

            # ✅ Display formatted response
            #st.markdown('<div class="response-container">', unsafe_allow_html=True)
            #st.markdown("### AI Response")
            #st.markdown(response_text)  # Full response first
            #st.markdown("</div>", unsafe_allow_html=True)

            # ✅ Step-wise Display with Grouped Sections
            st.markdown("### AI Response")

            sections = response_text.split("\n\n")  # Split response into sections

            for idx, section in enumerate(sections):
                st.markdown(f"#### {section}")

                if idx < len(image_urls):
                    st.image(image_urls[idx], caption=f"Relevant Image {idx+1}")
            
            
# ✅ Streamlit UI
st.title("Archibus AI")
st.markdown("Welcome to Archibus AI")

display_chat_history()

if prompt := st.chat_input("Ask me anything..."):
    handle_user_input(prompt)
