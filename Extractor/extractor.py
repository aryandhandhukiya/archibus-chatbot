import os
import json
import boto3
from botocore.exceptions import ClientError

# 🏷️ Configuration
AWS_ACCESS_KEY_ID = "AKIA2YICAKUAOHJUBRWM"
AWS_SECRET_ACCESS_KEY = "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"
EXTRACTED_IMAGES_FOLDER = "D:\\ArchibusV2\\extracted_images"  # Path to extracted images
MAPPING_FILE = "s3_upload/image_mapping.json"  # JSON output file
BUCKET_NAME = "archibus-chatbot-rag"  # Your S3 bucket name
REGION = "us-east-1"  # Replace with your AWS region if different

# 🔹 Initialize S3 Client and Resource
s3_client = boto3.client(
    "s3",
    region_name=REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)
s3_resource = boto3.resource(
    "s3",
    region_name=REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

# Function to check if versioning is enabled for the bucket
def is_versioning_enabled(bucket_name):
    try:
        response = s3_client.get_bucket_versioning(Bucket=bucket_name)
        status = response.get("Status", "Disabled")
        return status == "Enabled"
    except ClientError as e:
        print(f"Error checking versioning status: {e}")
        return False

# Function to delete all objects and versions from the bucket
def delete_all_objects(bucket_name):
    try:
        bucket = s3_resource.Bucket(bucket_name)
        
        # Check if versioning is enabled
        versioning_enabled = is_versioning_enabled(bucket_name)
        print(f"Versioning enabled: {versioning_enabled}")

        if versioning_enabled:
            # Delete all versions and delete markers
            print("Deleting all object versions and delete markers...")
            bucket.object_versions.delete()
        else:
            # Delete all objects (non-versioned)
            print("Deleting all objects...")
            bucket.objects.delete()

        print(f"All objects deleted from bucket {bucket_name}.")
        
        # Verify the bucket is empty
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        if "Contents" not in response:
            print(f"Bucket {bucket_name} is now empty.")
        else:
            print(f"Warning: Bucket {bucket_name} still contains objects.")

    except ClientError as e:
        print(f"Error deleting objects from bucket {bucket_name}: {e}")
        exit(1)

# Function to upload an image to S3 and return its URL
def upload_to_s3(image_path, image_name):
    """Uploads an image to S3 and returns its URL."""
    try:
        s3_client.upload_file(image_path, BUCKET_NAME, image_name, ExtraArgs={'ACL': 'public-read'})
        s3_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{image_name}"
        print(f"Uploaded {image_path} to {s3_url}")
        return s3_url
    except Exception as e:
        print(f"❌ Error uploading {image_name}: {e}")
        return None

# Function to process images and create mapping
def process_images():
    """Uploads all extracted images and creates a mapping file."""
    # Ensure the output directory for the mapping file exists
    os.makedirs(os.path.dirname(MAPPING_FILE), exist_ok=True)

    # Initialize the mapping dictionary
    image_mapping = {}

    # Iterate through all images in the extracted images folder
    for image_name in os.listdir(EXTRACTED_IMAGES_FOLDER):
        image_path = os.path.join(EXTRACTED_IMAGES_FOLDER, image_name)
        if os.path.isfile(image_path):
            # Get the absolute path of the image
            absolute_path = os.path.abspath(image_path).replace("\\", "\\\\")
            
            # Upload the image to S3
            s3_url = upload_to_s3(image_path, image_name)
            if s3_url:
                # Add to the mapping
                image_mapping[absolute_path] = s3_url

    # Save the mapping file
    with open(MAPPING_FILE, "w", encoding="utf-8") as f:
        json.dump(image_mapping, f, indent=4)

    print(f"✅ Upload Complete! Mapping file saved at {MAPPING_FILE}")

# Main execution
if __name__ == "__main__":
    print(f"Starting process at 02:03 PM IST on Saturday, May 24, 2025...")
    
    # Step 1: Delete all objects from the S3 bucket
    # print(f"Deleting all objects from bucket {BUCKET_NAME}...")
    # delete_all_objects(BUCKET_NAME)

    # Step 2: Upload images and create mapping
    print(f"Uploading images from {EXTRACTED_IMAGES_FOLDER} and creating mapping...")
    process_images()