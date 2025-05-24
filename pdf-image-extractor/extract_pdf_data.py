import fitz  # PyMuPDF
import os
import json
from PIL import Image
import io

# Paths
PDF_PATH = "D:\\ArchiBusV1\\master_merged.pdf"  # Replace with your PDF path
OUTPUT_DIR = "D:\\ArchibusV2\\extracted_images"
DATASET_PATH = "D:\\ArchibusV2\\pdf_dataset.json"

# Create output directory for images
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Open the PDF
pdf_document = fitz.open(PDF_PATH)
dataset = []

# Process each page
for page_num in range(len(pdf_document)):
    page = pdf_document[page_num]
    
    # Extract text
    text = page.get_text("text")
    
    # Extract images
    images = page.get_images(full=True)
    image_list = []
    
    for img_index, img in enumerate(images):
        xref = img[0]
        base_image = pdf_document.extract_image(xref)
        image_bytes = base_image["image"]
        
        # Convert to PIL Image
        image = Image.open(io.BytesIO(image_bytes))
        
        # Save image to disk
        image_path = os.path.join(OUTPUT_DIR, f"page_{page_num}_img_{img_index}.png")
        image.save(image_path)
        
        # Add to image list
        image_list.append(image_path)
    
    # Add to dataset
    dataset.append({
        "page_number": page_num,
        "text": text,
        "images": image_list
    })

# Save dataset to JSON
with open(DATASET_PATH, "w") as f:
    json.dump(dataset, f, indent=4)

print(f"Extracted data saved to {DATASET_PATH}")