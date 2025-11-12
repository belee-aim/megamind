from datetime import datetime
from fastapi import APIRouter, Request, HTTPException
from langgraph.graph.state import CompiledStateGraph
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from megamind.models.requests import MinionRequest
from megamind.utils.streaming import stream_response_with_ping
from megamind.utils.config import settings
from megamind import prompts
from megamind.clients.frappe_client import FrappeClient

router = APIRouter()


def get_token_from_header(request: Request):
    """
    Extracts the Bearer token from the Authorization header in the request.
    """
    auth_header = request.headers.get("authorization")
    if not auth_header:
        raise HTTPException(status_code=400, detail="Authorization header not found")

    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=400, detail="Invalid authorization header format. Expected 'Bearer {token}'")

    token = auth_header.replace("Bearer ", "", 1)
    return token


async def _handle_minion_stream(
    request: Request,
    chat_request: MinionRequest,
    graph_name: str,
    prompt: str,
    thread_id: str,
):
    if not thread_id:
        raise HTTPException(status_code=400, detail="Thread ID not found in path")

    graph: CompiledStateGraph = getattr(request.app.state, graph_name)
    config = RunnableConfig(configurable={"thread_id": thread_id})

    checkpointer: AsyncPostgresSaver = request.app.state.checkpointer
    thread_state = await checkpointer.aget(config)
    messages = []

    if thread_state is None:
        access_token = get_token_from_header(request)
        frappe_client = FrappeClient(access_token=access_token)
        company = frappe_client.get_default_company()
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
        context_info = f"**Current Date and Time**: {current_datetime}\n\n"
        system_prompt = context_info + prompt.format(company=company)
        messages.append(SystemMessage(content=system_prompt))

    messages.append(HumanMessage(content=chat_request.question))

    inputs = {"messages": messages}

    return await stream_response_with_ping(
        graph, inputs, config, provider=settings.provider
    )


@router.post("/wiki/stream/{thread_id}")
async def wiki_stream(request: Request, chat_request: MinionRequest, thread_id: str):
    """
    Handles streaming chat requests for the wiki graph.
    """
    return await _handle_minion_stream(
        request,
        chat_request,
        "wiki_graph",
        prompts.wiki_agent_instructions,
        thread_id,
    )


@router.post("/document/stream/{thread_id}")
async def document_stream(
    request: Request, chat_request: MinionRequest, thread_id: str
):
    """
    Handles streaming chat requests for the document search graph.
    """
    return await _handle_minion_stream(
        request,
        chat_request,
        "document_search_graph",
        prompts.document_agent_instructions,
        thread_id,
    )
