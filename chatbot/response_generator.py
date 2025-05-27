import google.generativeai as genai
from sentence_transformers import SentenceTransformer, util
import torch
import os
from dotenv import load_dotenv
print(f"Current working directory: {os.getcwd()}")
print(f"Looking for query_handler in: {os.path.join(os.getcwd(), 'chatbot', 'query_handler.py')}")

load_dotenv()
API_KEY = os.getenv("API_KEY")

# Configure Generative AI
genai.configure(api_key=API_KEY)

# AI Model
generation_config = {
    "temperature": 0.7,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 4096
}

model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    generation_config=generation_config
)

# Add semantic search model
try:
    semantic_model = SentenceTransformer('all-MiniLM-L6-v2')
except Exception as e:
    print(f"Error loading semantic model: {str(e)}")
    semantic_model = None

# Base Instruction (Japanese)
BASE_INSTRUCTION = """
You are a professional AI assistant for Archibus.
Your name is Archibus AI.
Please answer user questions according to the following rules:

1. Questions related to Archibus: Explain specific functions and operation methods **in detail**.
2. Facility management, maintenance, and cost data: Provide **comprehensive** analysis and guidance.
3. Workflow automation: Change appropriate data based on command input **and provide clear explanations**.
4. Integration functions (Slack, Teams, Email): Explain how to link **step by step**.
5. Learning ability: Utilize past question history to provide more appropriate answers.

Always answer **thoroughly yet structured**, and follow the selected language:
- If the selected language is **Japanese**, respond in **Japanese**.
- If the selected language is **English**, respond in **English**.
"""

# Load additional instructions from Data.txt
data_file_path = "D:\\ArchiBusV2\\Data.txt"

if os.path.exists(data_file_path):
    with open(data_file_path, "r", encoding="utf-8") as file:
        additional_instructions = file.read().strip()
else:
    additional_instructions = ""

# Combine static system instruction with custom instruction
FULL_INSTRUCTION = f"{BASE_INSTRUCTION}\n\n{additional_instructions}"

def extract_image_requirements(text):
    """Extract image requirements from response text"""
    requirements = []
    lines = text.split('\n')
    for line in lines:
        if '[IMG_REQ:' in line:
            req = line[line.find('[IMG_REQ:')+9:line.find(']')].strip()
            requirements.append(req)
    return requirements

def score_image_relevance(requirement, prompt, semantic_model):
    """Score image relevance using semantic similarity (0-10 scale)"""
    try:
        if not semantic_model:
            return 8.0  # Default score if model not available
        
        req_embedding = semantic_model.encode(requirement, convert_to_tensor=True)
        prompt_embedding = semantic_model.encode(prompt, convert_to_tensor=True)
        
        similarity = util.pytorch_cos_sim(req_embedding, prompt_embedding)
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
            if keyword in requirement.lower():
                score = min(10, score * boost)
        
        return round(score, 2)
    except Exception as e:
        print(f"Error calculating relevance score: {str(e)}")
        return 8.0

def score_requirement(requirement):
    """Calculate technical score for image requirement based on keywords"""
    technical_keywords = {
        'diagram': 2.0,
        'flowchart': 2.0,
        'architecture': 1.8,
        'workflow': 1.6,
        'system': 1.4,
        'configuration': 1.4,
        'dashboard': 1.3,
        'integration': 1.5,
        'setup': 1.3,
        'interface': 1.2,
        'process': 1.2,
        'components': 1.3,
        'infrastructure': 1.4,
        'network': 1.3,
        'database': 1.3,
        'security': 1.4,
        'maintenance': 1.2,
        'monitoring': 1.2
    }
    
    base_score = 5.0
    requirement_lower = requirement.lower()
    
    for keyword, weight in technical_keywords.items():
        if keyword in requirement_lower:
            base_score += weight
    
    final_score = min(10.0, base_score)
    return round(final_score, 2)

def generate_response(prompt, language="Japanese", max_retries=3):
    """Generates detailed AI response with implementation steps"""
    try:
        detailed_prompt = f"""
You are Archibus AI, a specialized assistant for facility management systems.
Respond in {language} with a detailed and comprehensive answer.

When answering:
1. Start with a brief overview explaining the concept
2. Provide detailed explanations using paragraphs
3. Always include specific Archibus implementation steps:
   - List exact menu paths in Archibus (e.g., "Navigate to: Menu > Maintenance > Work Orders")
   - Explain each field that needs to be configured

4. Give practical examples using real scenarios
5. Conclusion
6. Use markdown formatting for better readability:
   - **bold** for important terms and menu items
   - * for bullet points
   - 1. 2. 3. for sequential steps
   - Add proper spacing between sections

Do not use any separator lines or headings.
Focus on practical, step-by-step implementation in Archibus.

User Query: {prompt}
"""

        for attempt in range(max_retries):
            try:
                chat_session = model.start_chat(history=[])
                response = chat_session.send_message(
                    detailed_prompt,
                    generation_config={
                        "temperature": 0.7,
                        "top_p": 0.95,
                        "top_k": 40,
                        "max_output_tokens": 4096,
                        "candidate_count": 1
                    }
                )
                
                response_text = response.text.replace('---', '').replace('___', '').replace('***', '')
                
                # Quality check
                min_length = 200 if language == "English" else 300
                if len(response_text) < min_length:
                    if attempt < max_retries - 1:
                        continue
                
                return {
                    "response": response_text,
                    "sections": 1
                }
                
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt == max_retries - 1:
                    raise
        
        error_msg = "システムエラーが発生しました。" if language == "Japanese" else "A system error occurred."
        return {"response": error_msg, "sections": 0}
                
    except Exception as e:
        print(f"Error generating response: {str(e)}")
        error_msg = "エラーが発生しました。" if language == "Japanese" else "An error occurred."
        return {"response": error_msg, "sections": 0}

def test_scoring():
    test_requirements = [
        "System architecture diagram showing main components",
        "Simple screenshot of the interface",
        "Detailed workflow flowchart for maintenance process",
        "Basic image of the dashboard",
    ]
    
    print("\nTesting requirement scoring:")
    for req in test_requirements:
        tech_score = score_requirement(req)
        print(f"\nRequirement: {req}")
        print(f"Technical Score: {tech_score}/10")

if __name__ == "__main__":
    test_scoring()