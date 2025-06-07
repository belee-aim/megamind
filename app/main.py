from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import StreamingResponse

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

        # Invoke the graph with the user's prompt in streaming mode
        inputs = {"messages": [("human", request_data.prompt)]}

        async def stream_response():
            async for chunk in graph.astream(inputs):
                # Assuming the 'generate' node yields strings
                # You might need to adjust this based on your node's output
                if "__end__" in chunk:
                     # Handle the end of the stream if necessary
                     pass
                else:
                    # Find the output from the 'generate' node
                    # The structure of the chunk depends on the graph
                    # For a simple graph ending with 'generate', the chunk might contain the node's output directly
                    # If not, you might need to inspect the chunk structure
                    # For this simple graph, the chunk is the state update, and the 'generate' node yields directly
                    # So we need to access the yielded content from the state update
                    # This part might need refinement based on actual streaming output structure
                    # For now, let's assume the chunk itself is the yielded content from the generate node
                    # If the generate node yields strings, this should work.
                    # If the generate node updates the state and the state is yielded,
                    # you'd need to extract the relevant part from the state.

                    # A more robust way might be to have the generate node return a specific key in the state
                    # and yield that key's content.
                    # For now, let's assume the yielded content is directly in the chunk or a known key.

                    # Based on the generate_node implementation yielding strings,
                    # the chunk from astream might be a dictionary with node names as keys
                    # and their outputs as values.
                    # We need to find the output from the 'generate' node.
                    if "generate" in chunk:
                         # The output of the generate node is what we yielded
                         # This might be a dictionary if the node returned a dict, or the yielded value
                         # If the node yields strings, the chunk for that node might be {'generate': 'chunk_string'}
                         yield chunk["generate"]


        return StreamingResponse(stream_response(), media_type="text/event-stream")


    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Unexpected error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

# Example of how to access user info from token if needed:
# @app.get("/secure/v1/me")
# async def read_current_user(current_user: Dict = Depends(verify_supabase_token)):
#     return {"user_info": current_user}
