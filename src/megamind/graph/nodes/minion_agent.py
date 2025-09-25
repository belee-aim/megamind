from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from loguru import logger

from megamind.configuration import Configuration
from megamind.graph.states import AgentState
from megamind.graph.tools.minion_tools import search_wiki, search_document


async def wiki_agent_node(state: AgentState, config: RunnableConfig):
    """
    A node that represents the wiki agent.
    """
    logger.debug("---WIKI AGENT NODE---")
    messages = state.get("messages", [])
    configurable = Configuration.from_runnable_config(config)

    llm = ChatGoogleGenerativeAI(model=configurable.query_generator_model)
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

    llm = ChatGoogleGenerativeAI(model=configurable.query_generator_model)
    tools = [search_document]
    response = await llm.bind_tools(tools).ainvoke(messages)

    return {"messages": [response]}
