from langchain_core.documents import Document
from typing import List, Annotated, TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages.utils import AnyMessage

class AgentState(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]
    team_ids: List[str]
    documents: List[Document]
    cookie: str | None
