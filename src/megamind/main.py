from contextlib import asynccontextmanager
from datetime import datetime
import asyncio
import io
import json
import pandas as pd
import sentry_sdk
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from langgraph.graph.state import CompiledStateGraph

from megamind.prompts import build_system_prompt
from megamind.clients.frappe_client import FrappeClient
from megamind.clients.zep_client import get_zep_client
from megamind.clients.zep_checkpoint_saver import ZepCheckpointSaver
from megamind.graph.nodes.integrations.reconciliation_model import merge_customer_data
from megamind.graph.workflows.megamind_graph import build_megamind_graph
from megamind.graph.workflows.role_generation_graph import (
    build_role_generation_graph,
)
from megamind.graph.workflows.wiki_graph import build_wiki_graph
from megamind.graph.workflows.document_search_graph import build_document_search_graph
from megamind.graph.workflows.document_extraction_graph import (
    build_document_extraction_graph,
)
from megamind.api.v1.minion import router as minion_router
from megamind.api.v1.document_extraction import router as document_extraction_router
from megamind.api.v1.zep import router as zep_router
from megamind.models.requests import ChatRequest, RoleGenerationRequest
from megamind.models.responses import MainResponse
from megamind.utils.logger import setup_logging
from megamind.utils.config import settings
from megamind.utils.streaming import stream_response_with_ping

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler for the FastAPI application.
    Initializes the connection pool and graphs, handles startup and shutdown.
    """
    logger.info("Starting application lifespan initialization")

    # Initialize Zep checkpointer
    try:
        logger.info("Initializing Zep checkpointer")
        zep_client = get_zep_client()

        if not zep_client.is_available():
            logger.error("Zep client not configured. ZEP_API_KEY is required for checkpointer.")
            raise RuntimeError("ZEP_API_KEY is required for checkpointer. Please set it in .env file.")

        checkpointer = ZepCheckpointSaver(zep_client=zep_client)
        await checkpointer.setup()  # No-op for Zep, but maintains interface
        logger.info("Zep checkpointer initialized successfully")

        # Build graphs
        logger.info("Building megamind graph")
        document_graph = await build_megamind_graph(checkpointer=checkpointer)
        logger.info("Megamind graph built successfully")

        logger.info("Building role generation graph")
        role_generation_graph = await build_role_generation_graph()
        logger.info("Role generation graph built successfully")

        logger.info("Building wiki graph")
        wiki_graph = await build_wiki_graph(checkpointer=checkpointer)
        logger.info("Wiki graph built successfully")

        logger.info("Building document search graph")
        document_search_graph = await build_document_search_graph(
            checkpointer=checkpointer
        )
        logger.info("Document search graph built successfully")

        logger.info("Building document extraction graph")
        document_extraction_graph = await build_document_extraction_graph()
        logger.info("Document extraction graph built successfully")

        # Store in app state
        app.state.checkpointer = checkpointer
        app.state.pool = pool
        app.state.stock_movement_graph = document_graph
        app.state.document_graph = document_graph
        app.state.role_generation_graph = role_generation_graph
        app.state.wiki_graph = wiki_graph
        app.state.document_search_graph = document_search_graph
        app.state.document_extraction_graph = document_extraction_graph
        app.state.startup_success = True

        logger.info("Application startup completed successfully")

    except Exception as e:
        logger.critical(f"Failed to initialize application: {e}")
        raise

    yield

    # Graceful shutdown
    logger.info("Shutting down application...")
    # No cleanup needed for Zep (cloud-based)
    logger.info("Application shutdown complete")


if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        send_default_pii=True,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        environment=settings.environment,
    )
    logger.info(
        f"Sentry initialized successfully (environment={settings.environment}, traces_sample_rate={settings.sentry_traces_sample_rate})"
    )
else:
    logger.info("Sentry DSN not configured, skipping Sentry initialization")

app = FastAPI(
    title="Megamindesu",
    description="A FastAPI microservice to interact with AI models",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://aimbe.aim.mn",
        "https://link.aim.mn",
        "http://localhost:3000",
        "https://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(minion_router, prefix="/api/v1", tags=["Minion"])
app.include_router(
    document_extraction_router, prefix="/api/v1", tags=["Document Extraction"]
)
app.include_router(zep_router, prefix="/api/v1", tags=["Zep Memory"])

app.mount("/static", StaticFiles(directory="src/megamind/static"), name="static")


@app.get("/chat-debug-tool")
async def get_chat_ui():
    return FileResponse("src/megamind/static/chat-debug-tool.html")


@app.get("/")
async def read_root():
    logger.info("Root endpoint accessed")
    return {"message": "Welcome to the Megamindesu API"}


def get_token_from_header(request: Request):
    """
    Extracts the Bearer token from the Authorization header in the request.
    """
    auth_header = request.headers.get("authorization")
    if not auth_header:
        logger.warning("Authorization header not found in request")
        raise HTTPException(status_code=400, detail="Authorization header not found")

    if not auth_header.startswith("Bearer "):
        logger.warning("Invalid authorization header format")
        raise HTTPException(
            status_code=400,
            detail="Invalid authorization header format. Expected 'Bearer {token}'",
        )

    token = auth_header.replace("Bearer ", "", 1)
    logger.debug("Successfully extracted access token from Authorization header")
    return token


async def _handle_chat_stream(
    request: Request,
    request_data: ChatRequest,
    thread: str,
):
    """
    Handles the common logic for streaming chat responses.
    Knowledge retrieval is handled by the LLM via tools.
    State persistence handled by Zep checkpointer.
    """
    logger.info(f"Handling chat stream for thread={thread}")

    if not thread:
        raise HTTPException(status_code=400, detail="Thread parameter is required")

    try:
        graph: CompiledStateGraph = request.app.state.document_graph
        config = RunnableConfig(configurable={"thread_id": thread})

        access_token = get_token_from_header(request)
        checkpointer = request.app.state.checkpointer
        thread_state = await checkpointer.aget(config)
        messages = []

        # Initialize system prompt if it's a new thread
        if thread_state is None:
            logger.debug(f"Initializing new thread: {thread}")

            # Get runtime values
            frappe_client = FrappeClient(access_token=access_token)
            company = frappe_client.get_default_company()
            user_info = frappe_client.get_current_user_info()
            current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")

            logger.debug(f"Using company: {company}")
            logger.info(f"User context loaded: {user_info.get('full_name', 'Unknown')} ({user_info.get('email', 'Unknown')})")
            logger.debug(f"Current datetime: {current_datetime}")

            # Build system prompt with user information (knowledge will be retrieved by LLM via tools)
            system_prompt = build_system_prompt(
                company=company,
                current_datetime=current_datetime,
                user_name=user_info.get("full_name", ""),
                user_email=user_info.get("email", ""),
                user_roles=user_info.get("roles", []),
                user_department=user_info.get("department", ""),
            )
            messages.append(SystemMessage(content=system_prompt))
            logger.debug(f"System prompt built for thread: {thread}")
        else:
            logger.debug(f"Continuing existing thread: {thread}")

        # Process interruption if any
        if request_data.interrupt_response:
            logger.debug(f"Processing interrupt response for thread: {thread}")
            if thread_state and thread_state["channel_values"]["messages"]:
                last_message = thread_state["channel_values"]["messages"][-1]
                if isinstance(last_message, AIMessage) and last_message.tool_calls:
                    logger.debug(
                        f"Resuming with interrupt response for thread: {thread}"
                    )
                    inputs = Command(
                        resume=request_data.interrupt_response.model_dump()
                    )
                    return await stream_response_with_ping(
                        graph, inputs, config, provider=settings.provider
                    )

            messages.append(
                HumanMessage(
                    content=json.dumps(request_data.interrupt_response.model_dump())
                )
            )

        # Add user's question to the message list
        if request_data.question:
            logger.debug(f"Processing user question for thread: {thread}")
            messages.append(HumanMessage(content=request_data.question))

        inputs = {
            "messages": messages,
            "access_token": access_token,
            "company": request_data.company,
        }

        logger.debug(f"Starting stream for thread: {thread}")
        return await stream_response_with_ping(
            graph, inputs, config, provider=settings.provider
        )

    except HTTPException as e:
        logger.error(f"HTTP error in chat stream: {e}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error in chat stream: {e}")
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@app.post("/api/v1/stream/{thread}")
async def stream(
    request: Request,
    request_data: ChatRequest,
    thread: str = None,
):
    """
    Endpoint to chat with Aimee AI assistant.
    Streams the response from the AI model with RAG-augmented knowledge.
    """
    logger.info(f"Chat endpoint called: thread={thread}")
    return await _handle_chat_stream(request, request_data, thread)


@app.get("/api/v1/thread/{thread_id}/state")
async def get_thread_state(
    request: Request,
    thread_id: str,
):
    """
    Check if a thread is currently interrupted and waiting for user consent.

    Returns:
        - is_interrupted: True if waiting at user_consent_node
        - waiting_at_node: Name of the node where execution is paused
        - pending_tool_call: Details of the tool call awaiting consent
        - thread_exists: Whether the thread exists
    """
    try:
        logger.info(f"Thread state check called: thread_id={thread_id}")

        graph: CompiledStateGraph = request.app.state.document_graph
        config = RunnableConfig(configurable={"thread_id": thread_id})

        # Get state snapshot from graph (not checkpointer)
        state = await graph.aget_state(config)

        # Check if thread exists
        if state is None or state.values is None:
            logger.debug(f"Thread {thread_id} not found")
            return JSONResponse(
                content=MainResponse(
                    message="Thread not found",
                    response={
                        "is_interrupted": False,
                        "waiting_at_node": None,
                        "pending_tool_call": None,
                        "thread_exists": False,
                    },
                ).model_dump()
            )

        # Check if interrupted at user_consent_node
        is_interrupted = "user_consent_node" in (state.next or ())
        waiting_at_node = state.next[0] if state.next else None

        # Extract pending tool call if interrupted
        pending_tool_call = None
        if is_interrupted and state.values.get("messages"):
            last_message = state.values["messages"][-1]
            if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                tool_call = last_message.tool_calls[0]
                pending_tool_call = {
                    "id": tool_call.get("id"),
                    "name": tool_call.get("name"),
                    "args": tool_call.get("args"),
                }

        logger.debug(
            f"Thread {thread_id} state: interrupted={is_interrupted}, node={waiting_at_node}"
        )

        return JSONResponse(
            content=MainResponse(
                message="Success",
                response={
                    "is_interrupted": is_interrupted,
                    "waiting_at_node": waiting_at_node,
                    "pending_tool_call": pending_tool_call,
                    "thread_exists": True,
                },
            ).model_dump()
        )

    except Exception as e:
        logger.error(f"Error checking thread state for {thread_id}: {e}")
        return JSONResponse(
            status_code=500,
            content=MainResponse(
                message="Error", error=f"Failed to check thread state: {str(e)}"
            ).model_dump(),
        )


@app.get("/api/v1/threads/{thread_id}/history")
async def get_thread_history(
    request: Request,
    thread_id: str,
    limit: int = 50,
):
    """
    Retrieve conversation history for a thread from PostgreSQL checkpointer.
    Returns all messages in chronological order.
    """
    try:
        logger.debug(f"Retrieving history for thread: {thread_id}")

        # Get checkpointer and config
        checkpointer: AsyncPostgresSaver = request.app.state.checkpointer
        config = RunnableConfig(configurable={"thread_id": thread_id})

        # Get thread state from checkpointer
        thread_state = await checkpointer.aget(config)

        if thread_state is None:
            raise HTTPException(
                status_code=404, detail=f"Thread {thread_id} not found"
            )

        # Extract messages from state
        messages = thread_state.get("channel_values", {}).get("messages", [])

        # Convert messages to serializable format
        history = []
        for msg in messages[-limit:]:  # Get last N messages
            if isinstance(msg, SystemMessage):
                history.append(
                    {
                        "role": "system",
                        "content": msg.content,
                        "type": "system",
                    }
                )
            elif isinstance(msg, HumanMessage):
                history.append(
                    {
                        "role": "user",
                        "content": msg.content,
                        "type": "human",
                    }
                )
            elif isinstance(msg, AIMessage):
                history.append(
                    {
                        "role": "assistant",
                        "content": msg.content,
                        "type": "ai",
                        "tool_calls": (
                            [
                                {
                                    "id": tc.get("id"),
                                    "name": tc.get("name"),
                                    "args": tc.get("args"),
                                }
                                for tc in (msg.tool_calls or [])
                            ]
                            if hasattr(msg, "tool_calls") and msg.tool_calls
                            else None
                        ),
                    }
                )
            elif isinstance(msg, ToolMessage):
                history.append(
                    {
                        "role": "tool",
                        "content": msg.content,
                        "type": "tool",
                        "tool_call_id": msg.tool_call_id,
                    }
                )

        logger.info(f"Retrieved {len(history)} messages for thread {thread_id}")

        return MainResponse(
            message=f"Retrieved {len(history)} messages",
            response={
                "thread_id": thread_id,
                "messages": history,
                "count": len(history),
            },
        ).model_dump()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving thread history: {e}")
        raise HTTPException(
            status_code=500,
            detail=MainResponse(
                message="Error",
                error=f"Failed to retrieve thread history: {str(e)}",
            ).model_dump(),
        )


@app.post("/api/v1/reconciliation/merge")
async def merge_api(
    formatted_bank_file: UploadFile = File(...),
    customers_file: UploadFile = File(...),
):
    logger.info(
        f"Reconciliation merge request received: bank_file={formatted_bank_file.filename}, customers_file={customers_file.filename}"
    )

    # Read uploaded Excel or CSV files
    try:
        if formatted_bank_file.filename.endswith(".csv"):
            formatted_bank_data = pd.read_csv(
                io.BytesIO(await formatted_bank_file.read())
            )
        else:
            formatted_bank_data = pd.read_excel(
                io.BytesIO(await formatted_bank_file.read())
            )
        logger.info(f"Loaded {len(formatted_bank_data)} rows from bank file")

        if customers_file.filename.endswith(".csv"):
            customers_data = pd.read_csv(io.BytesIO(await customers_file.read()))
        else:
            customers_data = pd.read_excel(io.BytesIO(await customers_file.read()))
        logger.info(f"Loaded {len(customers_data)} rows from customers file")

    except Exception as e:
        logger.error(f"Error reading reconciliation files: {e}")
        raise HTTPException(status_code=400, detail=f"Error reading file: {e}")

    # Call the merge function
    logger.info("Starting customer data merge")
    result_df = merge_customer_data(formatted_bank_data, customers_data)
    logger.info(f"Merge completed successfully: {len(result_df)} result rows")

    # Replace NaN with None for JSON compatibility
    result_df = result_df.replace({pd.NA: None, float("nan"): None})

    # Return top 5 for preview (or convert to JSON)
    return result_df.to_dict(orient="records")


@app.post("/api/v1/role-generation")
async def role_generation(
    request: Request,
    request_data: RoleGenerationRequest,
):
    """
    Endpoint to generate role permissions.
    """
    logger.info(f"Role generation request received: role_name={request_data.role_name}")

    try:
        graph: CompiledStateGraph = request.app.state.role_generation_graph
        access_token = get_token_from_header(request)
        inputs = {
            "role_name": request_data.role_name,
            "user_description": request_data.user_description,
            "access_token": access_token,
        }
        logger.debug(f"Role generation inputs: {inputs}")

        logger.info(f"Starting role generation for: {request_data.role_name}")
        final_state = await graph.ainvoke(inputs)
        logger.info(
            f"Role generation completed successfully for: {request_data.role_name}"
        )

        return MainResponse(
            response={
                "roles": final_state.get("generated_roles", "").roles,
                "description": final_state.get("permission_description", ""),
            }
        ).model_dump()

    except Exception as e:
        logger.error(f"Unexpected error in role generation endpoint: {e}")
        return JSONResponse(
            status_code=500,
            content=MainResponse(
                message="Error", error=f"An unexpected error occurred: {str(e)}"
            ).model_dump(),
        )
