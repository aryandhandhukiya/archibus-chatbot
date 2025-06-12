import sys
import os
import json
import faiss
import re
import numpy as np
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import uvicorn
from typing import List
from sentence_transformers import SentenceTransformer
import logging

# Add parent directory to sys.path for module imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from chatbot.response_generator import generate_response

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Load Dataset ===
DATASET_PATH = "./pdf_dataset.json"
EMBEDDINGS_PATH = "./text_embeddings.npy"
INDEX_PATH = "./text_index.faiss"

# Load dataset
try:
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)
    if not isinstance(dataset, list):
        logger.error("pdf_dataset.json must be a list")
        raise Exception("pdf_dataset.json must be a list")
    logger.info(f"Loaded dataset with {len(dataset)} entries")
    for i in range(min(len(dataset), 2)):
        logger.info(f"dataset[{i}] = {dataset[i]}")
except FileNotFoundError:
    logger.error("pdf_dataset.json not found")
    raise Exception("pdf_dataset.json not found")
except json.JSONDecodeError:
    logger.error("pdf_dataset.json is corrupted")
    raise Exception("pdf_dataset.json is corrupted")
except Exception as e:
    logger.error(f"Error loading pdf_dataset.json: {str(e)}")
    raise Exception(f"Error loading pdf_dataset.json: {str(e)}")

# Load embeddings and index
try:
    text_embeddings = np.load(EMBEDDINGS_PATH)
    text_index = faiss.read_index(INDEX_PATH)
    logger.info(f"Loaded EMBEDDINGS with shape {text_embeddings.shape}")
    logger.info(f"Loaded INDEX with {text_index.ntotal} vectors")
except FileNotFoundError:
    logger.error("Embedding or index file not found")
    raise Exception("Embedding or index file not found")
except Exception as e:
    logger.error(f"Error loading embeddings/index: {str(e)}")
    raise Exception(f"Error loading embeddings/index: {str(e)}")

# Extract texts and validate
texts = []
for entry in dataset:
    if not isinstance(entry, dict):
        logger.warning(f"Skipping invalid entry (not a dict): {entry}")
        continue
    if "text" not in entry:
        logger.warning(f"Skipping entry missing 'text' key: {entry}")
        continue
    texts.append(entry["text"])
logger.info(f"Extracted {len(texts)} texts")

# Validate data consistency
if len(texts) != len(dataset) or len(texts) != len(text_embeddings) or len(texts) != text_index.ntotal:
    logger.error(f"Data mismatch: texts has {len(texts)} entries, dataset has {len(dataset)} entries, "
                 f"EMBEDDINGS has {len(text_embeddings)} entries, INDEX has {text_index.ntotal} vectors")
    raise Exception("Data mismatch between texts, dataset, EMBEDDINGS, and INDEX")

# === Embedding Model Setup ===
text_embedder = SentenceTransformer('all-MiniLM-L6-v2')

app = FastAPI()

# === Request/Response Models ===
class QueryRequest(BaseModel):
    question: str
    language: str = "English"

class StepResponse(BaseModel):
    step_name: str
    step_text: str
    images: List[dict]
    best_image: dict | None

class QueryResponse(BaseModel):
    question: str
    intro_text: str | None
    steps: List[StepResponse]
    conclusion_text: str | None

# === Helper Functions ===
def split_response_into_steps(text_response: str):
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
    conclusion_text = conclusion_match.group(0).strip() if conclusion_match else None
    if conclusion_match:
        text_response = text_response[:conclusion_match.start()].strip()

    # Find all matches of step markers
    matches = list(re.finditer(step_pattern, text_response, re.IGNORECASE))
    
    if not matches:
        return text_response.strip(), [("Full Response", text_response.strip())], conclusion_text

    # Extract the introductory text (before the first step)
    intro_text = text_response[:matches[0].start()].strip() if matches else None

    # Split the response into steps based on matches
    steps = []
    step_dict = {}  # To track steps by name and merge duplicates
    for i, match in enumerate(matches):
        start_pos = match.start()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(text_response)
        step_text = text_response[start_pos:end_pos].strip()
        step_name = match.group().strip().rstrip(',')
        
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

def find_images_for_step(step_text: str, k: int = 2):
    step_embedding = text_embedder.encode([step_text], convert_to_numpy=True).astype(np.float32)
    D, I = text_index.search(step_embedding, k=k)
    logger.info(f"FAISS search for step '{step_text[:30]}...': Distances: {D[0]}, Indices: {I[0]}")
    
    matching_images = []
    for idx in I[0]:
        if idx < 0:
            logger.warning(f"Skipping invalid FAISS index {idx} (negative index)")
            continue
        if idx >= len(dataset):
            logger.warning(f"Skipping index {idx} as it exceeds dataset length {len(dataset)}")
            continue
        try:
            page_data = dataset[idx]
            page_number = page_data["page_number"]
            images = page_data.get("images", [])
            for img_path in images:
                img_filename = os.path.basename(img_path)
                try:
                    img_number = int(img_filename.split("_")[-1].replace(".png", ""))
                    matching_images.append({
                        "page": page_number,
                        "image": img_number,
                        "path": img_path
                    })
                except (IndexError, ValueError) as e:
                    logger.warning(f"Error parsing image path: {img_path} => {e}")
                    continue
        except Exception as e:
            logger.error(f"Error processing index {idx}: {str(e)}")
            continue
    
    # Fallback: If no images are found, search with a broader query
    if not matching_images:
        simplified_text = " ".join(step_text.split()[:5])  # Use first 5 words
        step_embedding = text_embedder.encode([simplified_text], convert_to_numpy=True).astype(np.float32)
        D, I = text_index.search(step_embedding, k=k)
        logger.info(f"Fallback FAISS search for step '{simplified_text}': Distances: {D[0]}, Indices: {I[0]}")
        for idx in I[0]:
            if idx < 0:
                logger.warning(f"Skipping invalid FAISS index {idx} (negative index)")
                continue
            if idx >= len(dataset):
                logger.warning(f"Skipping index {idx} as it exceeds dataset length {len(dataset)}")
                continue
            try:
                page_data = dataset[idx]
                page_number = page_data["page_number"]
                images = page_data.get("images", [])
                for img_path in images:
                    img_filename = os.path.basename(img_path)
                    try:
                        img_number = int(img_filename.split("_")[-1].replace(".png", ""))
                        matching_images.append({
                            "page": page_number,
                            "image": img_number,
                            "path": img_path
                        })
                    except (IndexError, ValueError) as e:
                        logger.warning(f"Error parsing image path: {img_path} => {e}")
                        continue
            except Exception as e:
                logger.error(f"Error processing index {idx}: {str(e)}")
                continue
    
    return matching_images[:1]  # Limit to 1 image per step

# === Routes ===
@app.post("/query", response_model=QueryResponse)
async def query_handler(request: QueryRequest):
    try:
        logger.info(f"Received query: {request.question}")
        response_data = generate_response(request.question, request.language)
        text_response = response_data["response"]
        intro_text, steps, conclusion_text = split_response_into_steps(text_response)

        final_steps = []
        used_images = set()  # To avoid duplicate images across steps
        for step_name, step_text in steps:
            matched_images = find_images_for_step(step_text, k=2)
            # Filter images to avoid duplicates
            unique_images = []
            for img in matched_images:
                image_key = (img["page"], img["image"])
                if image_key not in used_images:
                    used_images.add(image_key)
                    unique_images.append(img)
            best_image = unique_images[0] if unique_images else None
            final_steps.append({
                "step_name": step_name,
                "step_text": step_text,
                "images": unique_images,
                "best_image": best_image
            })

        return {
            "question": request.question,
            "intro_text": intro_text,
            "steps": final_steps,
            "conclusion_text": conclusion_text
        }

    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check(request: Request):
    logger.info(f"Health check request: Method={request.method}, Headers={dict(request.headers)}")
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("mcp_server:app", host="0.0.0.0", port=8000, reload=True)