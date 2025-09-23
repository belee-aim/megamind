from contextlib import asynccontextmanager
import asyncio
import io
import json
import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command
from langgraph.graph.state import CompiledStateGraph

from . import prompts
from megamind.clients.frappe_client import FrappeClient
from megamind.dynamic_prompts.core.models import SystemContext, ProviderInfo
from megamind.dynamic_prompts.core.registry import prompt_registry
from megamind.graph.nodes.integrations.reconciliation_model import merge_customer_data
from megamind.graph.workflows.admin_support_graph import build_admin_support_graph
from megamind.graph.workflows.bank_reconciliation_graph import (
    build_bank_reconciliation_graph,
)
from megamind.graph.workflows.document_graph import build_rag_graph
from megamind.graph.workflows.stock_movement_graph import build_stock_movement_graph
from megamind.graph.workflows.role_generation_graph import (
    build_role_generation_graph,
)
from megamind.models.requests import ChatRequest, RoleGenerationRequest
from megamind.models.responses import MainResponse
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
        try:
            await checkpointer.setup()
        except Exception as e:
            logger.info(f"Could not set up tables: {e}. Assuming they already exist.")
        document_graph = await build_rag_graph(checkpointer=checkpointer)

        admin_support_graph = await build_admin_support_graph(checkpointer=checkpointer)
        bank_reconciliation_graph = await build_bank_reconciliation_graph(
            checkpointer=checkpointer
        )
        role_generation_graph = await build_role_generation_graph()

        app.state.checkpointer = checkpointer

        app.state.stock_movement_graph = document_graph
        app.state.document_graph = document_graph
        app.state.admin_support_graph = admin_support_graph
        app.state.bank_reconciliation_graph = bank_reconciliation_graph
        app.state.role_generation_graph = role_generation_graph

        # Load the prompt registry on startup
        await prompt_registry.load()
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


async def stream_response_with_ping(graph, inputs, config):
    """
    Streams responses from the graph with a ping mechanism to keep the connection alive.
    """
    queue = asyncio.Queue()

    async def stream_producer():
        try:
            async for chunk, _ in graph.astream(inputs, config, stream_mode="messages"):
                if isinstance(chunk, AIMessage) and chunk.content:
                    await queue.put(chunk.content)
        except Exception as e:
            logger.error(f"Error in stream producer: {e}")
            await queue.put(f"Error: {e}")
        finally:
            await queue.put(None)  # Signal completion

    async def response_generator():
        producer_task = asyncio.create_task(stream_producer())
        while True:
            try:
                chunk = await asyncio.wait_for(queue.get(), timeout=2.0)
                if chunk is None:
                    yield "event: done\ndata: {}\n\n".encode("utf-8")
                    break
                event_str = "event: stream_event\n"
                for line in str(chunk).splitlines():
                    data_str = f"data: {line}\n"
                    yield (event_str + data_str).encode("utf-8")
                yield b"\n"
            except asyncio.TimeoutError:
                yield "event: ping\ndata: {}\n\n".encode("utf-8")
            except Exception as e:
                logger.error(f"Error in response generator: {e}")
                import json

                error_data = {"message": "An error occurred during the stream."}
                yield f"event: error\ndata: {json.dumps(error_data)}\n\n".encode(
                    "utf-8"
                )
                break
        await producer_task

    return StreamingResponse(response_generator(), media_type="text/event-stream")


async def _handle_chat_stream(
    request: Request,
    request_data: ChatRequest,
    thread: str,
    prompt_family: str,
):
    """
    Handles the common logic for streaming chat responses.
    """
    if not thread:
        raise HTTPException(status_code=400, detail="Thread parameter is required")

    try:
        graph: CompiledStateGraph = request.app.state.document_graph
        config = RunnableConfig(configurable={"thread_id": thread})

        cookie = request.headers.get("cookie")
        checkpointer: AsyncPostgresSaver = request.app.state.checkpointer
        thread_state = await checkpointer.aget(config)
        messages = []

        # Initialize system prompt if it's a new thread
        if thread_state is None:
            frappe_client = FrappeClient(cookie=cookie)
            runtime_placeholders = {}
            if prompt_family == "generic":
                teams = frappe_client.get_teams()
                runtime_placeholders["team_ids"] = [
                    team.get("name") for team in teams.values()
                ]
            else:
                runtime_placeholders["company"] = frappe_client.get_default_company()

            context = SystemContext(
                provider_info=ProviderInfo(family=prompt_family),
                runtime_placeholders=runtime_placeholders,
            )
            system_prompt = await prompt_registry.get(context)
            messages.append(SystemMessage(content=system_prompt))

        # Process interruption if any
        if request_data.interrupt_response:
            if thread_state and thread_state["channel_values"]["messages"]:
                last_message = thread_state["channel_values"]["messages"][-1]
                if isinstance(last_message, AIMessage) and last_message.tool_calls:
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
            messages.append(HumanMessage(content=request_data.question))

        inputs = {
            "messages": messages,
            "cookie": cookie,
            "company": request_data.company,
        }

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
    return await _handle_chat_stream(request, request_data, thread, "stock_movement")


@app.post("/api/v1/admin-support/stream/{thread}")
async def admin_support(
    request: Request,
    request_data: ChatRequest,
    thread: str = None,
):
    """
    Endpoint to chat with Admin Support AI Agent.
    Streams the response from the AI model.
    """

    if not thread:
        raise HTTPException(status_code=400, detail="Thread parameter is required")

    try:
        cookie = request.headers.get("cookie")
        graph: CompiledStateGraph = request.app.state.admin_support_graph
        inputs = {
            "messages": [HumanMessage(content=request_data.question)],
            "cookie": cookie,
        }
        config = RunnableConfig(configurable={"thread_id": thread})
        return await stream_response_with_ping(graph, inputs, config)

    except HTTPException as e:
        logger.error(f"Unexpected error in chat endpoint: {e}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {e}")
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@app.post("/api/v1/bank-reconciliation/stream/{thread}")
async def bank_reconciliation(
    request: Request,
    request_data: ChatRequest,
    thread: str = None,
):
    """
    Endpoint to chat with Bank Reconciliation AI Agent.
    Streams the response from the AI model.
    """

    if not thread:
        raise HTTPException(status_code=400, detail="Thread parameter is required")

    try:
        cookie = request.headers.get("cookie")
        graph: CompiledStateGraph = request.app.state.bank_reconciliation_graph
        inputs = {
            "messages": [HumanMessage(content=request_data.question)],
            "cookie": cookie,
        }
        config = RunnableConfig(configurable={"thread_id": thread})
        return await stream_response_with_ping(graph, inputs, config)

    except HTTPException as e:
        logger.error(f"Unexpected error in chat endpoint: {e}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {e}")
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@app.post("/api/v1/reconciliation/merge")
async def merge_api(
    formatted_bank_file: UploadFile = File(...),
    customers_file: UploadFile = File(...),
):
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

        if customers_file.filename.endswith(".csv"):
            customers_data = pd.read_csv(io.BytesIO(await customers_file.read()))
        else:
            customers_data = pd.read_excel(io.BytesIO(await customers_file.read()))

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading file: {e}")

    # Call the merge function
    result_df = merge_customer_data(formatted_bank_data, customers_data)

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
    try:
        graph: CompiledStateGraph = request.app.state.role_generation_graph
        inputs = {
            "role_name": request_data.role_name,
            "user_description": request_data.user_description,
            "cookie": request.headers.get("cookie"),
            "access_token": request.headers.get("authorization"),
        }
        logger.debug(f"Role generation inputs: {inputs}")
        final_state = await graph.ainvoke(inputs)
        return MainResponse(
            response={
                "roles": final_state.get("generated_roles", "").roles,
                "description": final_state.get("permission_description", ""),
            }
        ).model_dump()

    except Exception as e:
        logger.error(f"Unexpected error in role generation endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail=MainResponse(
                message="Error", error=f"An unexpected error occurred: {str(e)}"
            ).model_dump(),
        )
