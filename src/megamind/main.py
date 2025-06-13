from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage # Added AIMessage
from pydantic import BaseModel

from .graph import graph


import logging

class ChatRequest(BaseModel):
    question: str

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
    Endpoint to chat with AI models.
    Streams the response from the AI model.
    """
    
    try:
        # Invoke the graph to get the final state
        inputs = {
            "messages": [HumanMessage(content=request_data.question)],
            "question": request_data.question,
        }

        async def stream_response():
            async for chunk, _ in graph.astream(inputs, stream_mode="messages"):
                if isinstance(chunk, AIMessage) and chunk.content:
                    event_str = "event: stream_event\n"
                    for line in str(chunk.content).splitlines():
                        data_str = f"data: {line}\n"
                        yield (event_str + data_str).encode('utf-8')
                    yield "\n"

        return StreamingResponse(stream_response(), media_type="text/event-stream")


    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Unexpected error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
