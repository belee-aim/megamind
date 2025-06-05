from fastapi import FastAPI, Depends, HTTPException

from .models.requests import ChatRequest
from .models.responses import ChatResponse
from .auth import verify_supabase_token
from .gemini import call_gemini_chat

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Park",
    description="A FastAPI microservice to interact with AI models",
    version="0.1.0"
)

@app.get("/")
async def read_root():
    logger.info("Root endpoint accessed")
    return {"message": "Welcome to the Park"}

@app.post("/v1/chat", response_model=ChatResponse)
async def chat(
    request_data: ChatRequest
):
    """
    Protected endpoint to chat with AI models.
    Requires a valid Supabase JWT in the Authorization header.
    """
    
    try:
        ai_reply = await call_gemini_chat(request_data.prompt)

        if ai_reply.startswith("Error:"):
            raise HTTPException(status_code=500, detail=ai_reply)

        return ChatResponse(reply=ai_reply)
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Unexpected error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

# Example of how to access user info from token if needed:
# @app.get("/secure/v1/me")
# async def read_current_user(current_user: Dict = Depends(verify_supabase_token)):
#     return {"user_info": current_user}
