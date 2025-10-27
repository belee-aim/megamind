from langchain_core.runnables import RunnableConfig
from loguru import logger

from megamind.clients.mcp_client_manager import client_manager
from megamind.configuration import Configuration

from ..states import AgentState


async def megamind_agent_node(state: AgentState, config: RunnableConfig):
    """
    Generates a response using the configured LLM provider based on the retrieved documents and conversation history.
    """
    logger.debug("---RAG NODE---")
    configurable = Configuration.from_runnable_config(config)
    mcp_client = client_manager.get_client()

    messages = state.get("messages", [])

    llm = configurable.get_chat_model()
    mcp_tools = await mcp_client.get_tools()
    response = await llm.bind_tools(mcp_tools).ainvoke(messages)

    # Add access token to tool call args if present
    if response.tool_calls:
        access_token = state.get("access_token")
        for tool_call in response.tool_calls:
            tool_name = tool_call.get("name")
            if any(tool.name == tool_name for tool in mcp_tools):
                tool_call["args"]["user_token"] = access_token

    return {"messages": [response]}
