from typing import List, Annotated, TypedDict

from typing import List, Annotated, TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages.utils import AnyMessage


class AgentState(TypedDict):
    """Represents the state of our agent."""

    messages: Annotated[List[AnyMessage], add_messages]
