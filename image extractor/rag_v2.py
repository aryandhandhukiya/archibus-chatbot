import logging.config
import streamlit as st
import chromadb
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
import ollama
import fitz  # PyMuPDF
from PIL import Image
from io import BytesIO
import logging
from transformers import CLIPProcessor, CLIPModel
import pytesseract
import functools
from pydantic import BaseModel
from typing import Dict


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

class OCRInspectionResult (BaseModel):
    results: Dict[str, bool]

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
# Initialize embedding model and CLIP
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

def init_state():
    if "chroma_client" not in st.session_state:
        st.session_state.chroma_client = chromadb.PersistentClient(path="chroma_db")
        st.session_state.collection = st.session_state.chroma_client.get_or_create_collection(name="RagTuto")
    if "processed_files" not in st.session_state:
        st.session_state.processed_files = set()
    if "uploaded_file" not in st.session_state:
        st.session_state.uploaded_file = None
    if "extracted_images" not in st.session_state:
        st.session_state.extracted_images = {}
    if "extracted_text" not in st.session_state:
        st.session_state.extracted_text = {}
        
def ocr_image(image_bytes):
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    ocr_text = pytesseract.image_to_string(image)
    return ocr_text.strip()

import os
import logging
from PIL import Image
import fitz  # PyMuPDF
from io import BytesIO
from werkzeug.utils import secure_filename

def extract_images_from_pdf(pdf_bytes, pdf_name):
    # Secure filename and setup directory
    pdf_name = secure_filename(os.path.splitext(pdf_name)[0])
    save_dir = os.path.join("saved_images")
    os.makedirs(save_dir, exist_ok=True)

    # Initialize storage
    images = {}

    # Open PDF from bytes
    pdf_reader = fitz.open(stream=pdf_bytes, filetype="pdf")

    for page_num, page in enumerate(pdf_reader.pages(), start=1):
        img_list = page.get_images(full=True)
        page_image_paths = []

        for img_index, img in enumerate(img_list, start=1):
            xref = img[0]
            base_image = pdf_reader.extract_image(xref)
            image_bytes = base_image["image"]

            # Convert to image and save as PNG
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
            filename = f"img{page_num}_{img_index}.png"
            filepath = os.path.join(save_dir, filename)
            image.save(filepath, format="PNG")
            page_image_paths.append(filepath)

        if page_image_paths:
            images[page_num] = page_image_paths
            logging.info(f"Page {page_num} saved {len(page_image_paths)} image(s) to disk.")
        else:
            logging.warning(f"Page {page_num} had no images.")

    return images


def upload_and_embed_pdf(pdf_file):
    if pdf_file.name in st.session_state.processed_files:
        st.warning(f"⚠️ {pdf_file.name} is already processed.")
        return

    pdf_bytes = pdf_file.read()
    images = extract_images_from_pdf(pdf_bytes, pdf_file.name)
    st.session_state.extracted_images[pdf_file.name] = images

    pdf_reader = PdfReader(BytesIO(pdf_bytes))
    extracted_text = {}
    with st.status("🔍 Processing document...", expanded=True) as status:
        for page_num, page in enumerate(pdf_reader.pages, start=1):
            text = page.extract_text()
            if text:
                extracted_text[page_num] = text
                embedding = embedding_model.encode(text).tolist()
                embedding_id = f"{pdf_file.name}_{page_num}"
                st.session_state.collection.add(
                    documents=[text], embeddings=[embedding], ids=[embedding_id]
                )
                st.write(f"✅ Embedded page {page_num}")
        status.update(label="✅ Document processed successfully!", state="complete", expanded=False)
    st.session_state.extracted_text[pdf_file.name] = extracted_text
    st.session_state.processed_files.add(pdf_file.name)
    st.session_state.uploaded_file = pdf_file.name

def get_images_for_page(page_number):
    # Directory where images are saved
    image_dir = os.path.join("saved_images")  # Assuming images are stored in this folder
    image_paths = []

    # Look for all images for the specific page (matching img{page_number}_index.png)
    for filename in os.listdir(image_dir):
        if filename.startswith(f"img{page_number}_"):
            image_paths.append(os.path.join(image_dir, filename))

    if image_paths:
        logging.info(f"Retrieved {len(image_paths)} images for page {page_number}.")
    else:
        logging.warning(f"No images found for page {page_number}.")
    
    return image_paths


def query_classes_from_ollama(query, context):
    prompt = f"""Context:
{context}

Based on this, generate exactly 2 comma-separated class labels for visual understanding that match user's query: {query}. Only output the two classes like:
a photo of a keyboard, a photo of a screen"""
    response = ollama.chat(
        model="llama3.2",
        messages=[{"role": "system", "content": "Generate class names for CLIP."}, {"role": "user", "content": prompt}]
    )
    return response['message']['content'].strip().split(',')[:2]


def inspect_ocr_with_llama(query, ocr_texts, page_context):
    prompt = f"""
You are an intelligent assistant. Your job is to verify whether the OCR text from each image logically fits with the overall content of the PDF page.

- The page context below is taken from the same page all images were extracted from.
- Each image's OCR may show partial UI screenshots, readings, or objects. Some OCRs may be less complete, but still relevant if they match the page's theme or repeated elements.

--- PDF Page Context ---
{page_context}

--- OCR Texts from Images ---
{ocr_texts}

Compare each OCR text *to the page context*, not just to each other. Return a JSON object showing which OCR texts are contextually relevant.


Use only `true` or `false` — no explanation or extra content.
"""

    response = ollama.chat(
        messages=[
            {
                "role": "system",
                "content": "You evaluate if OCR texts from images are relevant to the PDF page context. Respond only with structured JSON."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        model='llama3.2',
        format=OCRInspectionResult.model_json_schema()
    )

    return OCRInspectionResult.model_validate_json(response.message.content)


from PIL import Image
from io import BytesIO
import logging

def clip_classify_images(image_paths, class_labels):
    classified_results = []

    for i, img_path in enumerate(image_paths):
        try:
            with open(img_path, "rb") as f:
                img_bytes = f.read()  # Read image as bytes

            image = Image.open(BytesIO(img_bytes)).convert("RGB")
            inputs = clip_processor(text=class_labels, images=image, return_tensors="pt", padding=True)

            st.write(f"\n📸 **Image {i + 1}**: Running through CLIP...")
            outputs = clip_model(**inputs)
            probs = outputs.logits_per_image.softmax(dim=1).detach().numpy()[0]
            logging.info(f"Image {i + 1}: Classifying with probabilities {probs}")

            st.markdown("📊 **CLIP Predictions:**")
            for label, prob in zip(class_labels, probs):
                st.markdown(f"- `{label.strip()}` → **{prob*100:.2f}%**")

            top_idx = int(probs.argmax())
            predicted_label = class_labels[top_idx].strip()
            confidence = probs[top_idx]
            classified_results.append((image, predicted_label, confidence))

        except Exception as e:
            logging.error(f"❌ Failed to classify image {img_path}: {e}")
            st.error(f"Could not classify image {img_path}: {e}")

    return classified_results



def chat_with_ollama(query):
    query_embedding = embedding_model.encode(query).tolist()
    closest_pages = st.session_state.collection.query(query_embeddings=[query_embedding], n_results=5)

    documents = closest_pages["documents"]
    ids = closest_pages["ids"]
    print("gtfhfhiddddd", ids)

    # 🔧 Flatten if documents are nested (like [['doc1', 'doc2', ...]])
    if isinstance(documents[0], list):
        documents = documents[0]
    if isinstance(ids[0], list):
        ids = ids[0]

    if not documents:
        return "No relevant context found.", [], [], []

    page_images = []
    ocr_texts = {}
    full_context = ""

    for i in range(len(documents)):
        doc_id = ids[i]
        context = documents[i]
        full_context += context + "\n"
        page_number = int(doc_id.split('_')[-1])

        images_for_page = get_images_for_page(page_number)
        page_images.extend(images_for_page)

        with st.expander(f"🧠 See Model Thinking Process for Page {page_number}", expanded=False):
            st.markdown(f"**🔎 Closest Page from DB:** `{doc_id}` (Page {page_number})")
            st.code(context, language="markdown")
            st.markdown("---")

    ocr_texts = {}
    for i, img_path in enumerate(page_images, start=1):
        # Read the image from the path as bytes
        with open(img_path, "rb") as f:
            img_bytes = f.read()
        text = ocr_image(img_bytes)
        ocr_texts[f"Image{i}"] = text

    print(f"Number of images to classify: {len(page_images)}")
    print("orc ouput",ocr_texts )
    inspect_ans = inspect_ocr_with_llama(query=query, ocr_texts=ocr_texts, page_context= full_context )
    print(inspect_ans)
    response = ollama.chat(
        model="llama3.2",
        messages=[
            {"role": "system", "content": "Use the provided context to answer the user's query."},
            {"role": "user", "content": f"Context:\n{full_context}\n\nQuestion: {query}"}
        ]
    )

    class_labels = query_classes_from_ollama(query, full_context)

    with st.expander("🏷️ Class Tags Generated from LLM", expanded=True):
        st.markdown("These were generated based on your query and page context:")
        st.markdown(" &nbsp; ".join([f"`{label.strip()}`" for label in class_labels]))

    image_results = clip_classify_images(page_images, class_labels)

    return response['message']['content'], image_results, class_labels, page_number


# === Streamlit UI ===
init_state()
st.set_page_config(page_title="📄 Visual Assist RAG", layout="wide")
st.title("📄🤖 Visual Assist Mode - RAG with Image Understanding")

uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])
if uploaded_file:
    upload_and_embed_pdf(uploaded_file)

if st.session_state.uploaded_file:
    st.write(f"📄 {st.session_state.uploaded_file} is ready for queries!")

user_query = st.text_input("Ask your question:")
if user_query:
    with st.spinner("Thinking..."):
        response, classified_images, class_labels, page_number = chat_with_ollama(user_query)

        st.subheader("💬 AI Answer:")
        st.write(response)

        st.markdown(f"🔗 Matched Page Number: **{page_number}**")

        if classified_images:
            st.subheader("🖼️ Image Classification Results")
            for idx, (img, label, prob) in enumerate(classified_images):
                with st.container():
                    cols = st.columns([1, 2])
                    with cols[0]:
                        st.image(img, caption=f"🧠 `{label}` ({prob*100:.2f}%)", use_container_width=True)
                    with cols[1]:
                        st.markdown(f"**Prediction:** `{label}`\n\n**Confidence:** {prob*100:.2f}%")
                        st.markdown("**Tags Considered:**")
                        st.markdown(" &nbsp; ".join([f"`{lbl.strip()}`" for lbl in class_labels]))
                    st.divider()
        else:
            st.info("No images were found for the relevant pages.")
