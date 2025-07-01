from typing import Literal
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from loguru import logger

from megamind.graph.schemas import Route
from megamind.graph.states import AgentState
from megamind.configuration import Configuration
from megamind.prompts import router_node_instructions
from megamind.utils.config import settings


def router_node(state: AgentState, config: RunnableConfig):
    """
    Routes the graph node either to the vision node or react node based on user query
    """
    logger.debug("---ROUTER NODE---")
    configurable = Configuration.from_runnable_config(config)
    messages = state.get("messages", "")

    if state.get("next_node"):
        logger.debug(f"Next node already set: {state['next_node']}")
        return {"next_node": state["next_node"]}

    # Extract the query from the last human message
    if not messages:
        raise ValueError("No messages found in the state.")

    last_message = messages[-1]
    if not isinstance(last_message, HumanMessage):
        raise ValueError("The last message must be a HumanMessage.")

    # Initialize LLM with tools
    llm = ChatGoogleGenerativeAI(
        model=configurable.router_model, api_key=settings.google_api_key
    )

    prompt = router_node_instructions.format(query=last_message.content)

    # Invoke the LLM with the current messages
    result = llm.with_structured_output(Route).invoke(prompt)

    return {"next_node": result.next_node}


def continue_to_agent(
    state: AgentState,
) -> Literal["rag_node", "agent_node"]:
    """
    Determines the next node based on the state.
    """
    return state.get("next_node")
