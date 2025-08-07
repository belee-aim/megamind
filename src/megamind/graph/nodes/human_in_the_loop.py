from typing import Dict, Any
from langgraph.types import interrupt
from loguru import logger
from langchain_core.messages import AIMessage, HumanMessage

from ..states import AgentState


def user_consent_node(state: AgentState) -> dict:
    """
    Awaits user consent before proceeding with a create, update, or delete action.
    It interrupts the graph execution and expects a dictionary response from the client
    that conforms to the InterruptResponse schema.
    """
    logger.debug("---User consent node---")
    last_message = state["messages"][-1]
    tool_call = last_message.tool_calls[0]

    # Interrupt the graph to ask for user approval.
    response = interrupt(tool_call)

    # The response from the client will be a dictionary matching the InterruptResponse schema.
    if isinstance(response, dict):
        response_type = response.get("type")
        args = response.get("args", {})

        if response_type == "accept":
            # User approved, continue with the original tool call.
            return {"user_consent_response": "approved"}

        elif response_type == "edit":
            # User approved with edits. Update the tool call with the new args.
            new_tool_call = tool_call.copy()
            new_tool_call["args"] = args

            messages = list(state["messages"][:-1])
            new_ai_message = AIMessage(
                content=last_message.content,
                tool_calls=[new_tool_call],
                id=last_message.id,
            )
            messages.append(new_ai_message)

            return {"messages": messages, "user_consent_response": "approved"}

    # Default to denial for "deny", "response", or any other case.
    denial_message = "User has denied the action."
    if isinstance(response, dict) and response.get("type") == "response":
        denial_message = f"User responded: {response.get('args')}"

    messages = state["messages"] + [HumanMessage(content=denial_message)]

    return {"messages": messages, "user_consent_response": "denied"}
