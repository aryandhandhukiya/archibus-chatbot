import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import os
from dotenv import load_dotenv

# Load the dataset
DATASET_PATH = "../pdf_dataset.json"
with open(DATASET_PATH, "r") as f:
    dataset = json.load(f)

# Initialize text embedder
text_embedder = SentenceTransformer('all-MiniLM-L6-v2')

# Extract texts from dataset and compute embeddings
texts = [entry["text"] for entry in dataset]
text_embeddings = text_embedder.encode(texts, convert_to_numpy=True)

# Build FAISS index for text matching
text_index = faiss.IndexFlatL2(text_embeddings.shape[1])
text_index.add(text_embeddings)

# Save the embeddings and index to disk
np.save("pdf-embeddings/text_embeddings.npy", text_embeddings)
faiss.write_index(text_index, "pdf-embeddings/text_index.faiss")

# Save the texts and dataset for reference
with open("pdf-embeddings/metadata.json", "w") as f:
    json.dump({"texts": texts, "dataset": dataset}, f, indent=4)

print("Precomputation complete. Embeddings and index saved.")