from typing import Optional
from pydantic import BaseModel

from megamind.graph.schemas import InterruptResponse


class ChatRequest(BaseModel):
    question: Optional[str] = None
    company: Optional[str] = None
    interrupt_response: Optional[InterruptResponse] = None


class RoleGenerationRequest(BaseModel):
    role_name: str
    user_description: str


class MinionRequest(BaseModel):
    question: str
