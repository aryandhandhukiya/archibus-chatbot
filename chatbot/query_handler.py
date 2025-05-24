import re
import chromadb
from sentence_transformers import SentenceTransformer
import os
import base64
from PIL import Image
import io
import logging
import requests
from sentence_transformers import util

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load ChromaDB with error handling
try:
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                          "Extractor", "s3_upload", "chromadb")
    logger.info(f"Using ChromaDB path: {db_path}")
    chroma_client = chromadb.PersistentClient(path=db_path)
    collection = chroma_client.get_or_create_collection(name="image_mapping_metadata")
except Exception as e:
    logger.error(f"Error initializing ChromaDB: {str(e)}")
    chroma_client = None
    collection = None

# Load embedding model with error handling
try:
    embed_model = SentenceTransformer("all-MiniLM-L6-v2")
except Exception as e:
    logger.error(f"Error loading embedding model: {str(e)}")
    embed_model = None

# Function to extract step number from metadata
def extract_step_number(metadata):
    """Extracts step number from metadata if present, else return a large number."""
    try:
        match = re.search(r"step\s*(\d+)", metadata.get("description", ""), re.IGNORECASE)
        return int(match.group(1)) if match else 999
    except Exception as e:
        logger.error(f"Error extracting step number: {str(e)}")
        return 999

# Function to score image relevance based on semantic similarity
def score_image_relevance(image_desc, requirement, embed_model):
    """Score image relevance using semantic similarity (0-10 scale)"""
    try:
        if not embed_model:
            return 8.0  # Default score if model not available
        
        req_embedding = embed_model.encode(requirement, convert_to_tensor=True)
        desc_embedding = embed_model.encode(image_desc, convert_to_tensor=True)
        
        similarity = util.pytorch_cos_sim(req_embedding, desc_embedding)
        score = float(similarity[0][0] * 10)
        
        technical_boost = {
            'diagram': 1.5,
            'flowchart': 1.5,
            'architecture': 1.2,
            'workflow': 1.3,
            'system': 1.1,
            'configuration': 1.2,
            'dashboard': 1.1,
            'integration': 1.3,
            'setup': 1.2
        }
        
        for keyword, boost in technical_boost.items():
            if keyword in requirement.lower() or keyword in image_desc.lower():
                score = min(10, score * boost)
        
        return round(score, 2)
    except Exception as e:
        logger.error(f"Error calculating relevance score: {str(e)}")
        return 8.0

def fetch_image_as_base64(image_url):
    """Fetch an image from a URL or local path and convert it to base64."""
    try:
        if image_url.startswith('http'):
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            img_data = response.content
        else:
            with open(image_url, 'rb') as f:
                img_data = f.read()
        
        img = Image.open(io.BytesIO(img_data))
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"
    except Exception as e:
        logger.error(f"Error fetching/converting image {image_url}: {str(e)}")
        return None

def find_relevant_images_for_steps(img_requirements, top_k_per_step=5):
    """
    Find images for each step's image requirement and return base64-encoded data with scores.
    
    Args:
        img_requirements (list): List of image requirement descriptions
        top_k_per_step (int): Number of candidate images to retrieve per requirement
    
    Returns:
        list: List of base64-encoded image strings and scores for relevant images
    """
    try:
        logger.info(f"Finding images for {len(img_requirements)} requirements: {img_requirements}")
        
        if not collection or not embed_model:
            logger.error("ChromaDB or embedding model not available")
            return [None] * len(img_requirements), [0.0] * len(img_requirements)
        
        image_base64s = []
        image_scores = []
        
        for idx, req in enumerate(img_requirements):
            logger.info(f"Processing requirement {idx + 1}: '{req}'")
            
            expanded_query = req
            if any(term in req.lower() for term in ['maintenance', 'procedure', 'setup', 'workflow']):
                expanded_query = f"{req} guide process workflow"
            
            query_embedding = embed_model.encode(expanded_query).tolist()
            
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k_per_step,
                include=["metadatas"]
            )
            
            logger.info(f"ChromaDB query for '{req}' returned {len(results.get('metadatas', []))} results")
            
            images_with_scores = []
            if results and "metadatas" in results:
                for metadata_list in results["metadatas"]:
                    for metadata in metadata_list:
                        if "s3_url" in metadata:
                            # Fallback to image_name or pdf_source if description/documents is missing
                            image_desc = metadata.get("description", metadata.get("document", metadata.get("image_name", metadata.get("pdf_source", ""))))
                            if not image_desc and "documents" in results and results["documents"]:
                                image_desc = results["documents"][0]  # Fallback to first document if multiple
                            relevancy_score = score_image_relevance(image_desc, req, embed_model) if image_desc else 0.0
                            step_num = extract_step_number(metadata)
                            images_with_scores.append((step_num, metadata["s3_url"], relevancy_score))
            
            # Sort by step number and relevance score
            sorted_images = sorted(images_with_scores, key=lambda x: (x[0], -x[2]))
            best_image = sorted_images[0] if sorted_images else None
            
            if best_image and best_image[2] >= 8.0:
                base64_data = fetch_image_as_base64(best_image[1])
                if base64_data:
                    image_base64s.append(base64_data)
                    image_scores.append(best_image[2])
                    logger.info(f"Added image for '{req}' with score {best_image[2]:.1f}, URL: {best_image[1]}")
                else:
                    image_base64s.append(None)
                    image_scores.append(0.0)
                    logger.warning(f"Failed to convert image for '{req}' despite high score, URL: {best_image[1]}")
            else:
                image_base64s.append(None)
                image_scores.append(0.0)
                logger.warning(f"No relevant image found for '{req}' or score < 8.0, Best score: {best_image[2] if best_image else 'None'}")
        
        logger.info(f"Processed {len([b64 for b64 in image_base64s if b64])} images successfully")
        return image_base64s, image_scores
        
    except Exception as e:
        logger.error(f"Error in find_relevant_images_for_steps: {str(e)}")
        return [None] * len(img_requirements), [0.0] * len(img_requirements)

# Keep the old function for backward compatibility if needed
def find_relevant_images(query, top_k=5):
    """Legacy function for single query image search."""
    logger.warning("Using legacy find_relevant_images function, consider using find_relevant_images_for_steps")
    try:
        if not collection or not embed_model:
            return []
        
        expanded_query = query
        if any(term in query.lower() for term in ['maintenance', 'procedure', 'setup']):
            expanded_query = f"{query} guide process workflow"
        
        query_embedding = embed_model.encode(expanded_query).tolist()
        
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["metadatas"]
        )
        
        images_with_scores = []
        if results and "metadatas" in results:
            for metadata_list in results["metadatas"]:
                for metadata in metadata_list:
                    if "s3_url" in metadata:
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
        
        sorted_images = sorted(images_with_scores, key=lambda x: (x[0], -x[2]))
        urls_list = [img_url for _, img_url, _ in sorted_images] if sorted_images else []
        
        image_urls = []
        for url in urls_list:
            if url:
                if url.startswith('http'):
                    image_urls.append(url)
                else:
                    try:
                        img = Image.open(url)
                        buffered = io.BytesIO()
                        img.save(buffered, format="PNG")
                        img_str = base64.b64encode(buffered.getvalue()).decode()
                        data_uri = f"data:image/png;base64,{img_str}"
                        image_urls.append(data_uri)
                    except Exception as img_err:
                        logger.error(f"Error processing image {url}: {img_err}")
                        continue
        
        return image_urls
    except Exception as e:
        logger.error(f"Error in find_relevant_images: {str(e)}")
        return []