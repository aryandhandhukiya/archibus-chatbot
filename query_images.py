import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from chatbot.response_generator import generate_response
import re
import os

# Load the dataset
DATASET_PATH = "./pdf_dataset.json"
with open(DATASET_PATH, "r") as f:
    dataset = json.load(f)

# Initialize text embedder for matching text responses
text_embedder = SentenceTransformer('all-MiniLM-L6-v2')

# Extract texts from dataset and index them
texts = [entry["text"] for entry in dataset]
text_embeddings = text_embedder.encode(texts, convert_to_numpy=True)

# Build FAISS index for text matching
text_index = faiss.IndexFlatL2(text_embeddings.shape[1])
text_index.add(text_embeddings)

# Function to dynamically split the text response into steps
def split_response_into_steps(text_response):
    # Define patterns for identifying steps
    # Pattern 1: Numbered steps (e.g., "1.", "2.", "1)", "2)")
    numbered_pattern = r'(\d+\.\s|\d+\)\s)'
    # Pattern 2: Transitional phrases (e.g., "First", "Next", "Finally", "Step 1")
    transitional_phrases = [
        r'First(?:,|\b)',
        r'Next(?:,|\b)',
        r'After that(?:,|\b)',
        r'Now(?:,|\b)',
        r'Finally(?:,|\b)',
        r'Step\s+\d+(?:,|\b)'
    ]
    transitional_pattern = '|'.join(transitional_phrases)

    # Combine patterns
    step_pattern = f'({numbered_pattern}|{transitional_pattern})'

    # Find all matches of step markers
    matches = list(re.finditer(step_pattern, text_response, re.IGNORECASE))
    
    if not matches:
        # If no steps are found, treat the entire response as a single step
        return [("Full Response", text_response.strip())]

    # Split the response into steps based on matches
    steps = []
    for i, match in enumerate(matches):
        start_pos = match.start()
        # Find the start of the next step (or end of text)
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(text_response)
        
        # Extract the step text
        step_text = text_response[start_pos:end_pos].strip()
        # Use the matched marker as the step name (cleaned up)
        step_name = match.group().strip()
        if step_name.endswith(","):
            step_name = step_name[:-1]
        steps.append((step_name, step_text))
    
    return steps

# Function to find images based on step text
def find_images_for_step(step_text, step_name, k=2):
    # Embed the step text
    step_embedding = text_embedder.encode([step_text], convert_to_numpy=True)
    
    # Search for the most similar text in the dataset
    D, I = text_index.search(step_embedding, k=k)  # Get top k matches
    
    # Collect images from the matching pages
    matching_images = []
    matched_pages = []
    
    for idx in I[0]:
        page_data = dataset[idx]
        page_number = page_data["page_number"]
        images = page_data["images"]
        matched_pages.append(page_number)
        
        # Extract image numbers from file paths
        for img_path in images:
            # Use os.path for platform-independent path handling
            img_filename = os.path.basename(img_path)  # e.g., "page_5_img_2.png"
            try:
                img_number = int(img_filename.split("_")[-1].replace(".png", ""))
                matching_images.append((page_number, img_number))
            except (IndexError, ValueError) as e:
                print(f"Error parsing image path {img_path}: {e}")
                continue
    
    return matching_images, matched_pages

# Main loop to handle user queries
def main():
    language = "English"  # Match with app.py's default if needed
    while True:
        # Get user input
        query = input("Enter your question (or 'exit' to quit): ")
        if query.lower() == "exit":
            break
        
        # Generate text response using the same function as app.py
        print("\nGenerating text response...\n")
        try:
            response_data = generate_response(query, language)
            text_response = response_data["response"]
        except Exception as e:
            print(f"Error generating response: {str(e)}")
            continue
        
        print("Text Response:")
        print(text_response)
        print("\nSearching for relevant images for each step...\n")
        
        # Split the response into steps
        steps = split_response_into_steps(text_response)
        
        # Find images for each step
        for step_name, step_text in steps:
            print(f"\nStep: {step_name}")
            matching_images, matched_pages = find_images_for_step(step_text, step_name, k=2)  # Get top 2 matches per step
            
            print(f"Matched Pages: {matched_pages}")
            if matching_images:
                print("Found matching images:")
                for page_num, img_num in matching_images:
                    print(f"Page {page_num}, Image {img_num}")
            else:
                print("No matching images found for this step. Possible reasons:")
                print("- No images associated with the matched pages.")
                print("- The step text may not match any content in the PDF dataset.")
        
        print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    main()