from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from loguru import logger

from megamind import prompts
from megamind.clients.manager import client_manager
from megamind.configuration import Configuration
from megamind.graph.tools import frappe_retriever

from ..states import AgentState


async def agent_node(state: AgentState, config: RunnableConfig):
    """
    Generates a response using the Google Generative AI LLM based on the retrieved documents and conversation history.
    """
    logger.debug("---AGENT NODE---")
    configurable = Configuration.from_runnable_config(config)
    mcp_client = client_manager.get_client()

    documents = state.get("documents", [])
    document_context = "\n".join([doc.page_content for doc in documents])
    system_prompt = prompts.generate_node_instructions.format(
        documents=document_context, team_ids=state.get("team_ids", [])
    )
    messages = [SystemMessage(content=system_prompt)] + state.get("messages", [])

    llm = ChatGoogleGenerativeAI(model=configurable.query_generator_model)
    mcp_tools = await mcp_client.get_tools()
    tools = [frappe_retriever] + [mcp_tools]
    response = await llm.bind_tools(tools).ainvoke(messages)

    return {"messages": [response]}
