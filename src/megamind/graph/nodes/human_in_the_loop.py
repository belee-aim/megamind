from typing import Literal
from langgraph.types import interrupt, Command
from loguru import logger

from ..states import AgentState


def user_consent_node(state: AgentState) -> Command[Literal["mcp_tools", "rag_node"]]:
    """
    Awaits user consent before proceeding with a create or update action.
    """
    logger.debug("---USER CONSENT NODE---")
    last_message = state["messages"][-1]
    tool_call = last_message.tool_calls[0]

    # Interrupt the graph and ask for approval
    response = interrupt(
        {
            "question": "Do you approve the following action? (yes/no)",
            "tool_call": tool_call,
        }
    )

    if str(response).lower() == "yes":
        return Command(goto="mcp_tools")
    else:
        return Command(goto="rag_node")
