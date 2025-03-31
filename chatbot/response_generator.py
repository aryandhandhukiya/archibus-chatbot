import google.generativeai as genai
import os

API_KEY = "AIzaSyAuQOFtD6OQe_iDyPcKftGEJ5LbToJyZK8"

# Configure Generative AI
genai.configure(api_key=API_KEY)

# AI Model
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 2048
}

model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    generation_config=generation_config
)

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

If the user does not specify a language, default to **Japanese**.
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

def generate_response(prompt, language="Japanese", max_retries=3):
    """Generates AI response based on user input and language selection with retry mechanism."""
    try:
        # Enhanced prompt with completion markers
        structured_prompt = f"""
{BASE_INSTRUCTION}

User Query: {prompt}
Language: {language}

Important:
- Provide a complete response
- End your response with "[END_OF_RESPONSE]"
- Include all relevant details
- Structure your answer with clear sections
"""

        for attempt in range(max_retries):
            try:
                chat_session = model.start_chat(history=[])
                response = chat_session.send_message(
                    structured_prompt,
                    generation_config={
                        **generation_config,
                        "max_output_tokens": 4096,  # Increased token limit
                        "stop_sequences": ["[END_OF_RESPONSE]"]
                    }
                )
                
                response_text = response.text
                
                # Verify response completion
                if not response_text.strip():
                    continue  # Retry if empty response
                    
                if "[END_OF_RESPONSE]" not in response_text:
                    response_text += "\n[END_OF_RESPONSE]"
                    
                # Clean up the response
                final_response = response_text.replace("[END_OF_RESPONSE]", "").strip()
                
                # Verify minimum response length
                if len(final_response) < 50:  # Adjust threshold as needed
                    continue  # Retry if response too short
                    
                return final_response
                
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt == max_retries - 1:
                    raise
                
        return "申し訳ございません。現在システムが混雑しています。もう一度お試しください。" if language == "Japanese" else \
               "I apologize. The system is currently busy. Please try again."
               
    except Exception as e:
        print(f"Error generating response: {str(e)}")
        return "エラーが発生しました。" if language == "Japanese" else "An error occurred."
