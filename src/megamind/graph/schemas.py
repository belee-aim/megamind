from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, Field


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


class InterruptResponse(BaseModel):
    """
    Interrupt response format
    """

    type: Literal["accept", "edit", "response", "deny"] = Field(
        description="A type of user response based on the interrupt"
    )

    args: Optional[Dict[str, Any] | str] = Field(
        description="User response data", default=None
    )
