from langchain_core.runnables import RunnableConfig
from langchain_core.messages import AIMessage, ToolMessage
from loguru import logger

from megamind.configuration import Configuration
from megamind.graph.states import AgentState
from megamind.graph.tools.minion_tools import search_wiki, search_document


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
        if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
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
                    id=msg.id if hasattr(msg, 'id') else None,
                )
                sanitized.append(clean_msg)
        else:
            sanitized.append(msg)

    return sanitized


async def wiki_agent_node(state: AgentState, config: RunnableConfig):
    """
    A node that represents the wiki agent.
    """
    logger.debug("---WIKI AGENT NODE---")
    messages = state.get("messages", [])
    configurable = Configuration.from_runnable_config(config)

    # Sanitize messages for Claude's strict tool call requirements
    messages = sanitize_messages_for_claude(messages)

    llm = configurable.get_chat_model()
    tools = [search_wiki]
    response = await llm.bind_tools(tools).ainvoke(messages)

    return {"messages": [response]}


async def document_agent_node(state: AgentState, config: RunnableConfig):
    """
    A node that represents the document agent.
    """
    logger.debug("---DOCUMENT AGENT NODE---")
    messages = state.get("messages", [])
    configurable = Configuration.from_runnable_config(config)

    # Sanitize messages for Claude's strict tool call requirements
    messages = sanitize_messages_for_claude(messages)

    llm = configurable.get_chat_model()
    tools = [search_document]
    response = await llm.bind_tools(tools).ainvoke(messages)

    return {"messages": [response]}
