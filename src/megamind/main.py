from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph.state import CompiledStateGraph

from megamind.graph.workflows.document_graph import build_rag_graph
from megamind.graph.workflows.stock_movement_graph import build_stock_movement_graph
from megamind.models.requests import ChatRequest
from megamind.utils.logger import setup_logging
from megamind.utils.config import settings

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # build the graph
    async with AsyncPostgresSaver.from_conn_string(
        settings.supabase_connection_string
    ) as checkpointer:
        # First time execution will create the necessary tables
        # await checkpointer.setup()
        stock_movement_graph = await build_stock_movement_graph(
            checkpointer=checkpointer
        )
        document_graph = await build_rag_graph(checkpointer=checkpointer)

        app.state.stock_movement_graph = stock_movement_graph
        app.state.document_graph = document_graph
        yield


app = FastAPI(
    title="Megamindesu",
    description="A FastAPI microservice to interact with AI models",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="src/megamind/static"), name="static")


@app.get("/chat-debug-tool")
async def get_chat_ui():
    return FileResponse("src/megamind/static/chat-debug-tool.html")


@app.get("/")
async def read_root():
    logger.info("Root endpoint accessed")
    return {"message": "Welcome to the Megamindesu API"}


def get_sid_from_cookie(request: Request):
    """
    Extracts the session ID from the cookie in the request.
    """
    sid = request.cookies.get("sid")
    if not sid:
        raise HTTPException(status_code=400, detail="Session ID not found in cookies")
    return sid


@app.post("/api/v1/stream")
async def stream(
    request: Request, request_data: ChatRequest, sid=Depends(get_sid_from_cookie)
):
    """
    Endpoint to chat with AI models.
    Streams the response from the AI model.
    """

    try:
        # Extract the cookie from the request
        cookie = request.headers.get("cookie")

        # build the graph
        graph: CompiledStateGraph = request.app.state.document_graph

        # Invoke the graph to get the final state
        inputs = {
            "messages": [HumanMessage(content=request_data.question)],
            "cookie": cookie,
            "next_node": request_data.direct_route,
        }
        config = RunnableConfig(configurable={"thread_id": sid})

        async def stream_response():
            try:
                async for chunk, _ in graph.astream(
                    inputs, config, stream_mode="messages"
                ):
                    if isinstance(chunk, AIMessage) and chunk.content:
                        event_str = "event: stream_event\n"
                        for line in str(chunk.content).splitlines():
                            data_str = f"data: {line}\n"
                            yield (event_str + data_str).encode("utf-8")
                        yield b"\n"

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


@app.post("/api/v1/stock-movement/stream")
async def stock_movement(
    request: Request, request_data: ChatRequest, sid=Depends(get_sid_from_cookie)
):
    """
    Endpoint to chat with Stock movement AI Agent.
    Streams the response from the AI model.
    """

    try:
        # Extract the cookie from the request
        cookie = request.headers.get("cookie")

        # build the graph
        graph: CompiledStateGraph = request.app.state.stock_movement_graph

        # Invoke the graph to get the final state
        inputs = {
            "messages": [HumanMessage(content=request_data.question)],
            "cookie": cookie,
            "next_node": request_data.direct_route,
        }
        config = RunnableConfig(configurable={"thread_id": sid})

        async def stream_response():
            try:
                async for chunk, _ in graph.astream(
                    inputs, config, stream_mode="messages"
                ):
                    if isinstance(chunk, AIMessage) and chunk.content:
                        event_str = "event: stream_event\n"
                        for line in str(chunk.content).splitlines():
                            data_str = f"data: {line}\n"
                            yield (event_str + data_str).encode("utf-8")
                        yield b"\n"

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
