from google import genai
from google.genai import types
from .config import settings


# For simplicity, using a specific model. This could be made configurable.
# Ensure you have access to this model version with your API key.
MODEL_NAME = "gemini-2.0-flash-001" 

async def call_gemini_chat(prompt: str) -> str:
    """
    Calls the Google Gemini API with the given prompt and returns the response.
    """
    client = genai.Client(api_key=settings.google_api_key)

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[
                types.UserContent(
                    parts=[types.Part.from_text(text=prompt)]
                )
            ],
        )
        
        # Basic error/safety check (can be expanded)
        if not response.text:
            return "Error: No content generated. Check safety ratings or prompt."
        
        return response.text
    except Exception as e:
        # Log the exception e for debugging
        print(f"Error calling Gemini API: {e}")
        return f"Error interacting with Gemini: {str(e)}"
