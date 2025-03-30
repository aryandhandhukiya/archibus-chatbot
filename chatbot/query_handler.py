import re
import chromadb
from sentence_transformers import SentenceTransformer

# Load ChromaDB
db_path = r"C:\Users\sriya\Programming\Projects\Archi\archibus-chatbot\Extractor\s3_upload\chromadb"
chroma_client = chromadb.PersistentClient(path=db_path)
collection = chroma_client.get_or_create_collection(name="image_mapping_metadata")

# Load embedding model
embed_model = SentenceTransformer("all-MiniLM-L6-v2")

def extract_step_number(metadata):
    """Extracts step number from metadata if present, else return a large number."""
    match = re.search(r"step\s*(\d+)", metadata.get("description", ""), re.IGNORECASE)
    return int(match.group(1)) if match else 999  # Default large number for unordered images

def find_relevant_images(prompt, top_k=5):
    """Finds the most relevant images based on user query, ensuring step order."""
    query_embedding = embed_model.encode(prompt).tolist()
    
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,  # Retrieve multiple images
        include=["metadatas"]
    )

    images_with_steps = []
    if results and "metadatas" in results:
        for metadata_list in results["metadatas"]:
            for metadata in metadata_list:
                if "s3_url" in metadata:
                    step_number = extract_step_number(metadata)
                    images_with_steps.append((step_number, metadata["s3_url"]))

    # Sort images by step number (Step 1 → Step 2 → Step 3)
    sorted_images = sorted(images_with_steps, key=lambda x: x[0])

    return [img_url for _, img_url in sorted_images] if sorted_images else None
