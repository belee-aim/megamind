from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.params import Query
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from loguru import logger

from megamind.clients.manager import client_manager
from megamind.graph import build_graph
from megamind.models.requests import ChatRequest
from megamind.utils.logger import setup_logging

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # build the graph
    graph = await build_graph()
    app.state.graph = graph
    yield


app = FastAPI(
    title="Megamindesu",
    description="A FastAPI microservice to interact with AI models",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
async def read_root():
    logger.info("Root endpoint accessed")
    return {"message": "Welcome to the Megamindesu API"}


@app.post("/api/v1/stream")
async def stream(
    request: Request,
    request_data: ChatRequest,
):
    """
    Endpoint to chat with AI models.
    Streams the response from the AI model.
    """

    try:
        # Extract the cookie from the request
        cookie = request.headers.get("cookie")

        # Invoke the graph to get the final state
        inputs = {
            "messages": [HumanMessage(content=request_data.question)],
            "cookie": cookie,
            "next_node": request_data.direct_route,
        }

        async def stream_response():
            graph = request.app.state.graph
            try:
                async for chunk, _ in graph.astream(inputs, stream_mode="messages"):
                    if isinstance(chunk, AIMessage) and chunk.content:
                        event_str = "event: stream_event\n"
                        for line in str(chunk.content).splitlines():
                            data_str = f"data: {line}\n"
                            yield (event_str + data_str).encode("utf-8")
                        yield "\n"

                # Signal the end of the stream to the client
                yield "event: done\ndata: {}\n\n".encode("utf-8")

            except Exception as e:
                logger.error(f"Error during SSE stream generation: {e}")
                # Send an error event to the client before closing
                import json

                error_data = {"message": "An error occurred during the stream."}
                yield f"event: error\ndata: {json.dumps(error_data)}\n\n".encode(
                    "utf-8"
                )

        return StreamingResponse(stream_response(), media_type="text/event-stream")

    except HTTPException as e:
        logger.error(f"Unexpected error in chat endpoint: {e}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {e}")
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )
