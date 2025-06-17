from langchain_core.messages import HumanMessage

def get_human_message(state):
    """
    Extracts the first human message from the state.
    """
    for message in state.get("messages", []):
        if isinstance(message, HumanMessage):
            return message

    return None