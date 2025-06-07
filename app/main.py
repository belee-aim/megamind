from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage # Added AIMessage

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

@app.post("/v1/chat") # Removed response_model for streaming
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
        inputs = {"messages": [("human", request_data.prompt)]}

        async def stream_response():
            
            async for chunk in graph.astream(inputs, stream_mode="messages"):
                token, _ = chunk
                if isinstance(token, AIMessage):
                    yield f"data: {token.content}\n\n"

        return StreamingResponse(stream_response(), media_type="text/event-stream")


    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Unexpected error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")