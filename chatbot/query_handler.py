import re
import chromadb
from sentence_transformers import SentenceTransformer
import os
import base64
from PIL import Image
import io

# Load ChromaDB with error handling
try:
    # Use relative path for better cross-platform compatibility
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                          "Extractor", "s3_upload", "chromadb")
    print(f"Using ChromaDB path: {db_path}")
    chroma_client = chromadb.PersistentClient(path=db_path)
    collection = chroma_client.get_or_create_collection(name="image_mapping_metadata")
except Exception as e:
    print(f"Error initializing ChromaDB: {str(e)}")
    # Create fallback variables
    chroma_client = None
    collection = None

# Load embedding model with error handling
try:
    embed_model = SentenceTransformer("all-MiniLM-L6-v2")
except Exception as e:
    print(f"Error loading embedding model: {str(e)}")
    embed_model = None

def extract_step_number(metadata):
    """Extracts step number from metadata if present, else return a large number."""
    try:
        match = re.search(r"step\s*(\d+)", metadata.get("description", ""), re.IGNORECASE)
        return int(match.group(1)) if match else 999  # Default large number for unordered images
    except Exception as e:
        print(f"Error extracting step number: {str(e)}")
        return 999

def find_relevant_images(query, top_k=5):
    """Find images relevant to the query with improved path handling."""
    try:
        print(f"Finding images for query: '{query}', requesting {top_k} results")
        
        # Check if dependencies are available
        if not collection or not embed_model:
            print("ChromaDB or embedding model not available")
            return []
        
        # Preprocess query to include maintenance terms
        expanded_query = query
        if any(term in query.lower() for term in ['maintenance', 'procedure', 'setup']):
            expanded_query = f"{query} guide process workflow"
        
        # Encode the query
        query_embedding = embed_model.encode(expanded_query).tolist()
        
        # Query the collection with increased results
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["metadatas"]
        )
        
        print(f"ChromaDB query returned {len(results.get('metadatas', []))} results")
        
        # Process and sort images
        images_with_scores = []
        if results and "metadatas" in results:
            for metadata_list in results["metadatas"]:
                for metadata in metadata_list:
                    if "s3_url" in metadata:
                        # Check if URL contains relevant keywords
                        url_lower = metadata["s3_url"].lower()
                        relevancy_boost = 1.0
                        if any(term in url_lower for term in ['maintenance', 'procedure', 'guide']):
                            relevancy_boost = 1.5
                        
                        step_num = extract_step_number(metadata)
                        images_with_scores.append((
                            step_num,
                            metadata["s3_url"],
                            relevancy_boost
                        ))
        
        # Sort by step number and relevancy boost
        sorted_images = sorted(images_with_scores, key=lambda x: (x[0], -x[2]))
        urls_list = [img_url for _, img_url, _ in sorted_images] if sorted_images else []
        
        # Process URLs
        image_urls = []
        for url in urls_list:
            if url:
                if url.startswith('http'):
                    image_urls.append(url)
                    print(f"Using web URL: {url}")
                else:
                    try:
                        img = Image.open(url)
                        buffered = io.BytesIO()
                        img.save(buffered, format="PNG")
                        img_str = base64.b64encode(buffered.getvalue()).decode()
                        data_uri = f"data:image/png;base64,{img_str}"
                        image_urls.append(data_uri)
                        print(f"Converted local file to data URI: {url}")
                    except Exception as img_err:
                        print(f"Error processing image {url}: {img_err}")
                        continue
        
        print(f"Processed {len(image_urls)} image URLs successfully")
        return image_urls
        
    except Exception as e:
        print(f"Error in find_relevant_images: {str(e)}")
        return []