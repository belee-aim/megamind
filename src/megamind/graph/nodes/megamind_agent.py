from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from loguru import logger

from megamind.clients.mcp_client_manager import client_manager
from megamind.configuration import Configuration

from ..states import AgentState


async def megamind_agent_node(state: AgentState, config: RunnableConfig):
    """
    Generates a response using the Google Generative AI LLM based on the retrieved documents and conversation history.
    """
    logger.debug("---RAG NODE---")
    configurable = Configuration.from_runnable_config(config)
    mcp_client = client_manager.get_client()

    messages = state.get("messages", [])

    llm = ChatGoogleGenerativeAI(model=configurable.query_generator_model)
    mcp_tools = await mcp_client.get_tools()
    response = await llm.bind_tools(mcp_tools).ainvoke(messages)

    # Add cookie to tool call args if present
    if response.tool_calls:
        cookie = state.get("cookie")
        for tool_call in response.tool_calls:
            tool_name = tool_call.get("name")
            if any(tool.name == tool_name for tool in mcp_tools):
                tool_call["args"]["user_token"] = cookie

    return {"messages": [response]}
