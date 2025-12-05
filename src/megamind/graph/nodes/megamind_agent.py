import time
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import AIMessage, ToolMessage
from loguru import logger

from megamind.clients.mcp_client_manager import client_manager
from megamind.configuration import Configuration
from megamind.graph.tools.titan_knowledge_tools import (
    search_erpnext_knowledge,
    get_erpnext_knowledge_by_id,
)

from ..states import AgentState


def sanitize_messages_for_claude(messages: list) -> list:
    """
    Sanitize messages to meet Claude's strict tool call requirements.

    Claude requires that every AIMessage with tool_calls must be immediately
    followed by a ToolMessage (or messages) containing the tool results.
    This function removes incomplete tool call sequences that would cause
    Claude to return a 400 error.

    Args:
        messages: List of LangChain messages

    Returns:
        List of sanitized messages safe for Claude
    """
    if not messages:
        return messages

    sanitized = []

    for i, msg in enumerate(messages):
        # Check if this is an AI message with tool calls
        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
            # Check if next message(s) are tool results
            has_tool_results = False

            if i + 1 < len(messages):
                # Check if next message is a ToolMessage
                next_msg = messages[i + 1]
                if isinstance(next_msg, ToolMessage):
                    has_tool_results = True

            if has_tool_results:
                # Valid sequence: AI with tool_calls → ToolMessage
                sanitized.append(msg)
            else:
                # Orphaned tool calls - create a new AI message without tool calls
                logger.warning(
                    f"Removing orphaned tool calls from AI message at index {i}"
                )
                # Create a copy of the message without tool_calls
                clean_msg = AIMessage(
                    content=msg.content,
                    id=msg.id if hasattr(msg, "id") else None,
                )
                sanitized.append(clean_msg)
        else:
            # Not an AI message with tool calls, keep as is
            sanitized.append(msg)

    return sanitized


async def megamind_agent_node(state: AgentState, config: RunnableConfig):
    """
    Generates a response using the configured LLM provider based on the retrieved documents and conversation history.
    """
    logger.debug("---RAG NODE---")

    # Track response start time
    response_start = time.time()

    configurable = Configuration.from_runnable_config(config)
    mcp_client = client_manager.get_client()

    messages = state.get("messages", [])

    # Sanitize messages for Claude's strict tool call requirements
    # This prevents 400 errors when tool_use blocks don't have corresponding tool_result blocks
    messages = sanitize_messages_for_claude(messages)

    llm = configurable.get_chat_model()
    mcp_tools = await mcp_client.get_tools()

    # Add Titan knowledge search tools
    titan_tools = [search_erpnext_knowledge, get_erpnext_knowledge_by_id]

    all_tools = mcp_tools + titan_tools

    # Track LLM invocation time
    llm_start = time.time()
    response = await llm.bind_tools(all_tools).ainvoke(messages)
    llm_end = time.time()

    # Calculate LLM latency
    llm_latency_ms = (llm_end - llm_start) * 1000

    # Count tool calls in response
    tool_call_count = len(response.tool_calls) if response.tool_calls else 0

    # Add access token to tool call args if present (only for MCP tools)
    if response.tool_calls:
        access_token = state.get("access_token")
        for tool_call in response.tool_calls:
            tool_name = tool_call.get("name")
            if any(tool.name == tool_name for tool in mcp_tools):
                tool_call["args"]["user_token"] = access_token

    # Calculate total response time
    response_end = time.time()
    total_response_time_ms = (response_end - response_start) * 1000

    # Log performance metrics
    logger.debug(
        f"Agent metrics: LLM latency={llm_latency_ms:.2f}ms, "
        f"tool_calls={tool_call_count}, total_time={total_response_time_ms:.2f}ms"
    )

    # Accumulate metrics in state (for knowledge capture analysis)
    # Get existing metrics or initialize
    existing_llm_latency = state.get("llm_latency_ms", 0) or 0
    existing_tool_calls = state.get("tool_call_count", 0) or 0
    existing_total_time = state.get("total_response_time_ms", 0) or 0

    return {
        "messages": [response],
        "response_start_time": response_start,
        "llm_latency_ms": existing_llm_latency + llm_latency_ms,
        "tool_call_count": existing_tool_calls + tool_call_count,
        "total_response_time_ms": existing_total_time + total_response_time_ms,
    }
