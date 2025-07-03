from typing import Literal
from pydantic import BaseModel, Field


class Route(BaseModel):
    next_node: Literal["rag_node", "agent_node", "stock_movement_agent_node"] = Field(
        description="The next node to route the query to: 'rag_node', 'agent_node', or 'stock_movement_agent_node'."
    )
