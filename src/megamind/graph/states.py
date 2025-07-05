from langchain_core.documents import Document
from typing import List, Annotated, Literal, TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages.utils import AnyMessage


class AgentState(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]
    team_ids: List[str]
    documents: List[Document]
    cookie: str | None
    company: str | None
    last_stock_entry_id: str | None
    next_node: Literal["rag_node", "agent_node", "stock_movement_agent_node"] | None
