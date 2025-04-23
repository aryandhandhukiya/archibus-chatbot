from sentence_transformers import SentenceTransformer, util
import torch
import re
from .image_utils import ImageProcessor
import requests
from PIL import Image
from io import BytesIO

class SemanticImageSearch:
    def __init__(self, collection):
        self.collection = collection
        self.embed_model = SentenceTransformer("all-MiniLM-L6-v2")
        self.image_processor = ImageProcessor()
        self.standard_width = 400  # Standard width for all images
        self.max_height = 300      # Maximum height for all images
        
    def process_and_resize_image(self, image_url):
        """Process and resize image to standard dimensions"""
        try:
            response = requests.get(image_url)
            img = Image.open(BytesIO(response.content))
            
            # Calculate new dimensions
            aspect_ratio = img.width / img.height
            new_width = self.standard_width
            new_height = int(new_width / aspect_ratio)
            
            # Adjust if height exceeds max
            if new_height > self.max_height:
                new_height = self.max_height
                new_width = int(new_height * aspect_ratio)
            
            # Resize image
            resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            return resized_img, image_url
            
        except Exception as e:
            print(f"Error processing image {image_url}: {str(e)}")
            return None, None
        
    def process_image(self, image_bytes):
        """Process image for better quality"""
        try:
            image = Image.open(BytesIO(image_bytes))
            
            # Set minimum dimensions for better quality
            min_width = 800
            if image.size[0] < min_width:
                ratio = min_width / image.size[0]
                new_size = (min_width, int(image.size[1] * ratio))
                image = image.resize(new_size, Image.Resampling.LANCZOS)
            
            # Convert to RGB if needed
            if image.mode in ('RGBA', 'P'):
                image = image.convert('RGB')
            
            # Save with high quality
            img_byte_arr = BytesIO()
            image.save(img_byte_arr, format='PNG', quality=95, optimize=True)
            img_byte_arr.seek(0)
            return img_byte_arr.getvalue()
            
        except Exception as e:
            print(f"Error processing image: {str(e)}")
            return image_bytes
        
    def semantic_search(self, query, metadata, threshold=0.3):
        """Perform semantic search between query and image metadata"""
        try:
            # Combine metadata fields
            metadata_text = ' '.join([
                metadata.get('description', ''),
                metadata.get('title', ''),
                metadata.get('content', ''),
                re.sub(r'[_\-.]', ' ', metadata.get('s3_url', '').split('/')[-1])
            ]).lower()
            
            # Calculate similarity
            query_embedding = self.embed_model.encode(query, convert_to_tensor=True)
            text_embedding = self.embed_model.encode(metadata_text, convert_to_tensor=True)
            
            similarity = float(util.pytorch_cos_sim(query_embedding, text_embedding)[0][0])
            return similarity
        except Exception as e:
            print(f"Similarity calculation error: {str(e)}")
            return 0.0
    
    def find_relevant_images(self, requirements, top_k=3):
        """Find semantically relevant images for each requirement"""
        relevant_images = []
        
        for requirement in requirements:
            try:
                results = self.collection.query(
                    query_embeddings=[self.embed_model.encode(requirement).tolist()],
                    n_results=top_k * 3,
                    include=["metadatas", "distances"]
                )
                
                if not results or "metadatas" not in results:
                    continue
                    
                scored_images = []
                for metadata in results["metadatas"][0]:
                    if "s3_url" in metadata:
                        similarity = self.semantic_search(requirement, metadata)
                        if similarity >= 0.3:
                            scored_images.append((metadata["s3_url"], similarity))
                
                scored_images.sort(key=lambda x: x[1], reverse=True)
                
                for url, similarity in scored_images[:top_k]:
                    processed_image, image_url = self.process_and_resize_image(url)
                    if processed_image:
                        relevant_images.append(processed_image)
                    else:
                        print(f"Skipping image {url} due to processing error")
                
            except Exception as e:
                print(f"Error processing requirement '{requirement}': {str(e)}")
                continue
        
        return relevant_images