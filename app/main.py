from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage # Added AIMessage

from .models.requests import ChatRequest
from .models.responses import ChatResponse
from .auth import verify_supabase_token
from .graph.builder import build_graph

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

@app.post("/api/v1/chat") 
async def chat(
    request_data: ChatRequest
):
    """
    Protected endpoint to chat with AI models.
    Requires a valid Supabase JWT in the Authorization header.
    Streams the response from the AI model.
    """
    
    try:
        # Build the graph
        graph = build_graph()

        # Invoke the graph to get the final state
        user_id = "12345" # Placeholder for user ID
        inputs = {
            "messages": [HumanMessage(content=request_data.question)],
            "user_id": user_id,
            "question": request_data.question,
        }

        async def stream_response():
            
            async for chunk in graph.astream(inputs):
                if "messages" in chunk:
                    last_message = chunk["messages"][-1]
                    if isinstance(last_message, AIMessage):
                        yield f"data: {last_message.content}\n\n"

        return StreamingResponse(stream_response(), media_type="text/event-stream")


    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Unexpected error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")