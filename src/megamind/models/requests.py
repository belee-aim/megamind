from typing import Literal
from pydantic import BaseModel


class ChatRequest(BaseModel):
    question: str
    company: str | None = None
