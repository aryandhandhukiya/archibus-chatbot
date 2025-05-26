import json

# Configuration
METADATA_FILE = "D:\\ArchibusV2\\archibus-chatbot\\pdf-embeddings\\metadata.json"  # Path to your metadata.json file
MAPPING_FILE = "s3_upload/image_mapping.json"  # Path to the image_mapping.json file

# Load the image mapping
try:
    with open(MAPPING_FILE, "r", encoding="utf-8") as f:
        image_mapping = json.load(f)
except FileNotFoundError:
    print(f"Mapping file {MAPPING_FILE} not found.")
    exit(1)
except json.JSONDecodeError as e:
    print(f"Error decoding JSON from {MAPPING_FILE}: {e}")
    exit(1)

# Load the metadata
try:
    with open(METADATA_FILE, "r", encoding="utf-8") as f:
        metadata = json.load(f)
except FileNotFoundError:
    print(f"Metadata file {METADATA_FILE} not found.")
    exit(1)
except json.JSONDecodeError as e:
    print(f"Error decoding JSON from {METADATA_FILE}: {e}")
    exit(1)

# Update the dataset within metadata with S3 URLs
dataset = metadata.get("dataset", [])
for page_entry in dataset:
    images = page_entry.get("images", [])
    updated_images = []
    
    for image_path in images:
        # Normalize the image path to match the mapping file format (double backslashes)
        normalized_path = image_path.replace("\\", "\\\\")
        
        # Check if the normalized image path exists in the mapping
        if normalized_path in image_mapping:
            s3_url = image_mapping[normalized_path]
            updated_images.append(s3_url)
            print(f"Replaced {image_path} with {s3_url}")
        else:
            print(f"Warning: No S3 URL found for {image_path}. Keeping original path.")
            updated_images.append(image_path)
    
    # Update the images list
    page_entry["images"] = updated_images

# Save the updated metadata back to the JSON file
with open(METADATA_FILE, "w", encoding="utf-8") as f:
    json.dump(metadata, f, indent=4, ensure_ascii=False)

print(f"Updated metadata saved to {METADATA_FILE} at 05:47 PM IST on Saturday, May 24, 2025.")