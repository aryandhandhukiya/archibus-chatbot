import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import os
from dotenv import load_dotenv

# Load the dataset
DATASET_PATH = "../pdf_dataset.json"
with open(DATASET_PATH, "r", encoding="utf-8") as f:
    dataset = json.load(f)

# Initialize text embedder
text_embedder = SentenceTransformer('all-MiniLM-L6-v2')

# Extract texts from dataset and compute embeddings
texts = [entry["text"] for entry in dataset]
text_embeddings = text_embedder.encode(texts, convert_to_numpy=True)

# Build FAISS index for text matching
text_index = faiss.IndexFlatL2(text_embeddings.shape[1])
text_index.add(text_embeddings)

# Ensure the output directory exists
output_dir = "pdf-embeddings"
os.makedirs(output_dir, exist_ok=True)

# Save the embeddings and index to disk
np.save(os.path.join(output_dir, "text_embeddings.npy"), text_embeddings)
faiss.write_index(text_index, os.path.join(output_dir, "text_index.faiss"))

# Save the texts and dataset for reference
with open(os.path.join(output_dir, "metadata.json"), "w", encoding="utf-8") as f:
    json.dump({"texts": texts, "dataset": dataset}, f, indent=4)

print("Precomputation complete. Embeddings and index saved at 05:52 PM IST on Saturday, May 24, 2025.")