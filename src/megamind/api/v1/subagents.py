"""Subagent-based streaming API endpoint.

Uses the new SubAgentMiddleware-based graph instead of the
traditional LangGraph orchestrator-worker pattern.
"""

from datetime import datetime
import json

from fastapi import APIRouter, HTTPException, Request
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from loguru import logger

from megamind.clients.frappe_client import FrappeClient
from megamind.clients.zep_client import get_zep_client
from megamind.models.requests import ChatRequest
from megamind.prompts.subagent_prompts import USER_CONTEXT_TEMPLATE
from megamind.utils.config import settings
from megamind.utils.request_context import set_access_token, set_thread_id
from megamind.utils.streaming import stream_response_with_ping


router = APIRouter(prefix="/subagents", tags=["Subagents"])


def _get_token_from_header(request: Request) -> str:
    """Extract Bearer token from Authorization header."""
    auth_header = request.headers.get("authorization")
    if not auth_header:
        raise HTTPException(status_code=400, detail="Authorization header not found")

    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=400,
            detail="Invalid authorization header format. Expected 'Bearer {token}'",
        )

    return auth_header.replace("Bearer ", "", 1)


@router.post("/stream/{thread}")
async def stream_subagent(
    request: Request,
    request_data: ChatRequest,
    thread: str,
):
    """
    Streaming chat endpoint using the SubAgentMiddleware-based architecture.

    This endpoint uses the new subagent pattern where specialists are invoked
    via a `task` tool rather than explicit LangGraph routing.
    """
    logger.info(f"Subagent stream called: thread={thread}")

    if not thread:
        raise HTTPException(status_code=400, detail="Thread parameter is required")

    try:
        access_token = _get_token_from_header(request)

        # Set access token in request context for tools to read at runtime
        set_access_token(access_token)

        # Set thread_id in request context for ConsentMiddleware Firebase integration
        set_thread_id(thread)

        # Get user context
        frappe_client = FrappeClient(access_token=access_token)
        company = frappe_client.get_default_company()
        user_info = frappe_client.get_current_user_info()
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")

        logger.debug(
            f"User: {user_info.get('full_name', 'Unknown')} ({user_info.get('email', 'Unknown')})"
        )

        # Setup Zep for knowledge graph
        zep_client = get_zep_client()
        user_id = None

        if zep_client.is_available():
            try:
                user_id = user_info.get("email") or user_info.get("name")
                if user_id:
                    await zep_client.get_or_create_user(
                        user_id=user_id,
                        email=user_info.get("email", ""),
                        first_name=user_info.get("first_name", ""),
                        last_name=user_info.get("last_name", ""),
                    )
                    await zep_client.get_or_create_thread(
                        thread_id=thread,
                        user_id=user_id,
                    )
            except Exception as e:
                logger.warning(f"Failed to setup Zep user/thread: {e}")
                user_id = None

        # Fetch user context from Zep knowledge graph (for dynamic system prompt)
        user_context = ""
        if zep_client.is_available() and user_id and request_data.query:
            try:
                user_context_results = await zep_client.search_graph(
                    query=request_data.query,
                    user_id=user_id,
                    limit=5,  # Keep it small for speed
                )
                logger.debug(f"User context results: {user_context_results}")
                if user_context_results:
                    context_parts = ["## User Context (Personal Knowledge)"]
                    for item in user_context_results:
                        fact = item.get("fact", "")
                        if fact:
                            context_parts.append(f"- {fact}")
                    user_context = "\n".join(context_parts)
                    logger.debug(
                        f"Fetched user context: {len(user_context_results)} facts"
                    )
            except Exception as e:
                logger.warning(f"Failed to fetch user context from Zep: {e}")

        # Get pre-built subagent graph from app state
        graph: CompiledStateGraph = request.app.state.subagent_graph

        # Build config with user context for dynamic system prompt
        config = RunnableConfig(
            configurable={
                "thread_id": thread,
                "company": company,
                "current_datetime": current_datetime,
                "user_name": user_info.get("full_name", ""),
                "user_email": user_info.get("email", ""),
                "user_roles": user_info.get("roles", []),
                "user_department": user_info.get("department", ""),
                "user_context": user_context,  # Passed to build_orchestrator_system_prompt
            }
        )

        # Get thread state for interrupt handling and context check
        checkpointer = request.app.state.checkpointer
        thread_state = await checkpointer.aget(config) if checkpointer else None
        existing_messages = (
            thread_state.get("channel_values", {}).get("messages", [])
            if thread_state
            else []
        )

        # Check if context message already exists (only add once per thread)
        has_context_message = any(
            isinstance(msg, SystemMessage)
            and "## Current Session Context" in (msg.content or "")
            for msg in existing_messages
        )

        messages = []

        # Add combined context as SystemMessage if not already in thread
        if not has_context_message:
            roles_str = ", ".join(user_info.get("roles", [])) or "N/A"
            context_message = USER_CONTEXT_TEMPLATE.format(
                user_name=user_info.get("full_name", "N/A"),
                user_email=user_info.get("email", "N/A"),
                user_roles=roles_str,
                user_department=user_info.get("department", "N/A"),
                company=company or "N/A",
                current_datetime=current_datetime,
                user_context=user_context,
            )
            messages.append(SystemMessage(content=context_message))

        # Handle interrupt response
        if request_data.interrupt_response:
            logger.debug(f"Processing interrupt response for thread: {thread}")

            if existing_messages:
                last_message = existing_messages[-1]
                if hasattr(last_message, "tool_calls") and last_message.tool_calls:
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

        # Add user query
        if request_data.query:
            logger.debug(f"Processing query for thread: {thread}")
            messages.append(HumanMessage(content=request_data.query))

            # Sync to Zep
            if zep_client.is_available() and user_id:
                try:
                    await zep_client.add_message(
                        thread_id=thread,
                        role="user",
                        content=request_data.query,
                    )
                except Exception as e:
                    logger.warning(f"Failed to sync message to Zep: {e}")

        inputs = {
            "messages": messages,
            "access_token": access_token,
        }

        logger.debug(f"Starting subagent stream for thread: {thread}")
        return await stream_response_with_ping(
            graph,
            inputs,
            config,
            provider=settings.provider,
            zep_client=zep_client if zep_client.is_available() else None,
            zep_thread_id=thread,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in subagent stream: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}",
        )
