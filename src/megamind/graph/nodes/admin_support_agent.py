from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from loguru import logger

from megamind import prompts
from megamind.clients.mcp_client_manager import client_manager
from megamind.configuration import Configuration

from ..states import AgentState


async def admin_support_agent_node(state: AgentState, config: RunnableConfig):
    """
    Specialized agent for handling administrative support tasks in ERPNext.
    Focuses on administrative functions, such as managing user accounts, permissions, and system settings.
    Only uses ERPNext MCP tools - no document retrieval functionality.
    """
    logger.debug("---ADMIN SUPPORT AGENT NODE---")
    configurable = Configuration.from_runnable_config(config)
    mcp_client = client_manager.get_client()

    # No document context needed - this agent only handles ERPNext operations
    company = state.get("company") or "Aimlink"
    system_prompt = prompts.admin_support_agent_instructions.format(
        company=company,
    )
    messages = [SystemMessage(content=system_prompt)] + state.get("messages", [])

    llm = ChatGoogleGenerativeAI(model=configurable.query_generator_model)
    # Only use ERPNext MCP tools - no frappe_retriever
    mcp_tools = await mcp_client.get_tools()

    response = await llm.bind_tools(mcp_tools).ainvoke(messages)

    return {
        "messages": [response],
        "company": company,
    }
