from typing import Any, List, Annotated, TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages.utils import AnyMessage
from langchain_core.documents import Document

class AgentState(TypedDict):
    """Represents the state of our agent."""

    messages: Annotated[List[AnyMessage], add_messages]
    team_ids: List[str]
    question: str
    documents: List[Document]
    vector_store: Any
