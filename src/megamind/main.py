from contextlib import asynccontextmanager
import io
import json
import pandas as pd
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command
from langgraph.graph.state import CompiledStateGraph

from megamind.clients.frappe_client import FrappeClient
from megamind.dynamic_prompts.core.models import SystemContext, ProviderInfo
from megamind.dynamic_prompts.core.registry import prompt_registry
from megamind.graph.nodes.integrations.reconciliation_model import merge_customer_data
from megamind.graph.workflows.megamind_graph import build_megamind_graph
from megamind.graph.workflows.role_generation_graph import (
    build_role_generation_graph,
)
from megamind.graph.workflows.wiki_graph import build_wiki_graph
from megamind.graph.workflows.document_search_graph import build_document_search_graph
from megamind.api.v1.minion import router as minion_router
from megamind.api.v1.document_extraction import router as document_extraction_router
from megamind.models.requests import ChatRequest, RoleGenerationRequest
from megamind.models.responses import MainResponse
from megamind.utils.logger import setup_logging
from megamind.utils.config import settings
from megamind.utils.streaming import stream_response_with_ping

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application lifespan initialization")
    # build the graph
    async with AsyncPostgresSaver.from_conn_string(
        settings.supabase_connection_string
    ) as checkpointer:
        # First time execution will create the necessary tables
        try:
            logger.info("Setting up checkpointer tables")
            await checkpointer.setup()
            logger.info("Checkpointer tables setup completed")
        except Exception as e:
            logger.info(f"Could not set up tables: {e}. Assuming they already exist.")

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

        app.state.checkpointer = checkpointer

        app.state.stock_movement_graph = document_graph
        app.state.document_graph = document_graph
        app.state.role_generation_graph = role_generation_graph
        app.state.wiki_graph = wiki_graph
        app.state.document_search_graph = document_search_graph

        # Load the prompt registry on startup
        logger.info("Loading prompt registry")
        await prompt_registry.load()
        logger.info("Prompt registry loaded successfully")

        logger.info("Application startup completed successfully")
        yield
        logger.info("Application shutdown initiated")


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

app.include_router(minion_router, prefix="/api/v1", tags=["Minion"])
app.include_router(
    document_extraction_router, prefix="/api/v1", tags=["Document Extraction"]
)

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
    prompt_family: str,
):
    """
    Handles the common logic for streaming chat responses.
    """
    logger.info(
        f"Handling chat stream for thread={thread}, prompt_family={prompt_family}"
    )

    if not thread:
        raise HTTPException(status_code=400, detail="Thread parameter is required")

    try:
        graph: CompiledStateGraph = request.app.state.document_graph
        config = RunnableConfig(configurable={"thread_id": thread})

        access_token = get_token_from_header(request)
        checkpointer: AsyncPostgresSaver = request.app.state.checkpointer
        thread_state = await checkpointer.aget(config)
        messages = []

        # Initialize system prompt if it's a new thread
        if thread_state is None:
            logger.debug(
                f"Initializing new thread: {thread} with prompt_family: {prompt_family}"
            )
            frappe_client = FrappeClient(access_token=access_token)
            runtime_placeholders = {}
            runtime_placeholders["company"] = frappe_client.get_default_company()
            logger.debug(f"Using company: {runtime_placeholders['company']}")

            context = SystemContext(
                provider_info=ProviderInfo(family=prompt_family),
                runtime_placeholders=runtime_placeholders,
            )
            system_prompt = await prompt_registry.get(context)
            messages.append(SystemMessage(content=system_prompt))
            logger.debug(f"System prompt loaded for thread: {thread}")
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
                    return await stream_response_with_ping(graph, inputs, config)

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
        return await stream_response_with_ping(graph, inputs, config)

    except HTTPException as e:
        logger.error(f"HTTP error in chat stream for {prompt_family}: {e}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error in chat stream for {prompt_family}: {e}")
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
    Endpoint to chat with AI models.
    Streams the response from the AI model.
    """
    logger.info(f"Generic chat endpoint called: thread={thread}")
    return await _handle_chat_stream(request, request_data, thread, "generic")


@app.post("/api/v1/accounting-finance/stream/{thread}")
async def accounting_finance(
    request: Request,
    request_data: ChatRequest,
    thread: str = None,
):
    """
    Endpoint to chat with Accounting and Finance AI Agent.
    Streams the response from the AI model.
    """
    logger.info(f"Accounting & Finance endpoint called: thread={thread}")
    return await _handle_chat_stream(
        request, request_data, thread, "accounting_finance"
    )


@app.post("/api/v1/stock-movement/stream/{thread}")
async def stock_movement(
    request: Request,
    request_data: ChatRequest,
    thread: str = None,
):
    """
    Endpoint to chat with Stock movement AI Agent.
    Streams the response from the AI model.
    """
    logger.info(f"Stock Movement endpoint called: thread={thread}")
    return await _handle_chat_stream(request, request_data, thread, "stock_movement")


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
