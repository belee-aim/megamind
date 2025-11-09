from typing import Any
from pydantic import BaseModel, Field


class MainResponse(BaseModel):
    message: str = "Success"
    error: str | None = None
    response: Any | None = None


class ThreadStateResponse(BaseModel):
    """Response model for thread state check"""
    is_interrupted: bool = Field(description="Whether the thread is currently interrupted")
    waiting_at_node: str | None = Field(description="Name of the node where execution is paused", default=None)
    pending_tool_call: dict | None = Field(description="Details of the pending tool call if interrupted", default=None)
    thread_exists: bool = Field(description="Whether the thread exists in the checkpoint")
