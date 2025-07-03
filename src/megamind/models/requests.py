from typing import Literal
from pydantic import BaseModel


class ChatRequest(BaseModel):
    question: str
    direct_route: Literal["rag_node", "agent_node", "stock_movement_agent_node"] | None = None
