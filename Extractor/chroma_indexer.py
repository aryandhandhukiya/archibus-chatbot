import json
import chromadb
from sentence_transformers import SentenceTransformer

# Load ChromaDB
db_path = "D:\\ARCHIBUSV2\\Extractor\\s3_upload\\chromadb"
chroma_client = chromadb.PersistentClient(path=db_path)
collection = chroma_client.get_or_create_collection(name="image_mapping_metadata")

# Load embedding model
embed_model = SentenceTransformer("all-MiniLM-L6-v2")

# Load metadata
metadata_file = "D:\\ARCHIBUSV2\\Extractor\\s3_upload\\image_mapping.json"  # Absolute path
with open(metadata_file, "r") as f:
    image_metadata = json.load(f)

# Index metadata in ChromaDB
for entry in image_metadata:
    description = entry.get("description", entry.get("pdf_source", "No description available"))
    embedding = embed_model.encode(description).tolist()
    collection.add(
        ids=[entry["image_name"]],
        embeddings=[embedding],
        metadatas=[entry],
        documents=[description]
    )

print("✅ ChromaDB Indexing Complete!")