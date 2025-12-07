from langchain_core.runnables import RunnableConfig
from langchain_core.messages import AIMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from loguru import logger

from megamind.configuration import Configuration
from megamind.graph.states import AgentState
from megamind.graph.tools.minion_tools import search_document
from megamind.utils.config import settings


def sanitize_messages_for_claude(messages: list) -> list:
    """
    Sanitize messages to meet Claude's strict tool call requirements.

    Claude requires that every AIMessage with tool_calls must be immediately
    followed by a ToolMessage containing the tool results.
    """
    if not messages:
        return messages

    sanitized = []

    for i, msg in enumerate(messages):
        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
            has_tool_results = False

            if i + 1 < len(messages):
                next_msg = messages[i + 1]
                if isinstance(next_msg, ToolMessage):
                    has_tool_results = True

            if has_tool_results:
                sanitized.append(msg)
            else:
                logger.warning(
                    f"Removing orphaned tool calls from AI message at index {i}"
                )
                clean_msg = AIMessage(
                    content=msg.content,
                    id=msg.id if hasattr(msg, "id") else None,
                )
                sanitized.append(clean_msg)
        else:
            sanitized.append(msg)

    return sanitized


async def document_agent_node(state: AgentState, config: RunnableConfig):
    """
    A node that represents the document agent.
    """
    logger.debug("---DOCUMENT AGENT NODE---")
    messages = state.get("messages", [])
    configuration = Configuration()

    # Sanitize messages for Claude's strict tool call requirements
    messages = sanitize_messages_for_claude(messages)

    llm = ChatGoogleGenerativeAI(
        model=configuration.fast_model,
        google_api_key=settings.google_api_key,
    )
    tools = [search_document]
    response = await llm.bind_tools(tools, parallel_tool_calls=True).ainvoke(messages)

    return {"messages": [response]}
