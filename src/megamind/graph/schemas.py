from typing import Literal
from pydantic import BaseModel, Field


class Route(BaseModel):
    next_node: Literal[
        "rag_node", "agent_node", "stock_movement_agent_node", "admin_support_agent_node", "bank_reconciliation_agent_node"
    ] = Field(
        description="The next node to route the query to: 'rag_node', 'agent_node', 'stock_movement_agent_node', 'admin_support_agent_node', or 'bank_reconciliation_agent_node'."
    )


class ConversationSummary(BaseModel):
    """
    A summary of a conversation, including general content, key points, and structured data.
    """

    general_content: str = Field(
        description="A brief, general summary of the conversation."
    )
    key_points: list[str] = Field(
        description="A list of the most important points or takeaways from the conversation."
    )
    structured_data: dict = Field(
        description="Any structured data that was extracted from the conversation, such as form data or API call arguments."
    )
