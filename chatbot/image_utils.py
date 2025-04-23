from PIL import Image
import requests
from io import BytesIO

class ImageProcessor:
    def __init__(self):
        self.target_width = 600
        self.max_height = 800
        self.min_width = 400
        self.quality = 85

    def process_image(self, image_url):
        """Process image to ensure consistent size and quality"""
        try:
            # Load image from URL
            response = requests.get(image_url)
            img = Image.open(BytesIO(response.content))
            
            # Convert to RGB if needed
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Calculate new dimensions maintaining aspect ratio
            aspect_ratio = img.width / img.height
            new_width = self.target_width
            new_height = int(new_width / aspect_ratio)
            
            # Adjust height if it exceeds max_height
            if new_height > self.max_height:
                new_height = self.max_height
                new_width = int(new_height * aspect_ratio)
            
            # Ensure minimum width
            if new_width < self.min_width:
                new_width = self.min_width
                new_height = int(new_width / aspect_ratio)
            
            # Resize image
            resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Save to BytesIO with compression
            output = BytesIO()
            resized_img.save(output, format='JPEG', quality=self.quality)
            output.seek(0)
            
            return output
            
        except Exception as e:
            print(f"Error processing image: {str(e)}")
            return None