from typing import Optional
from pydantic import BaseModel

from megamind.graph.schemas import InterruptResponse


class ChatRequest(BaseModel):
    query: Optional[str] = None
    company: Optional[str] = None
    interrupt_response: Optional[InterruptResponse] = None


class RoleGenerationRequest(BaseModel):
    role_name: str
    user_description: str


class MinionRequest(BaseModel):
    query: str


class DocumentRequestBody(BaseModel):
    file_id: str
    file_name: str


class DocumentExtractionRequest(BaseModel):
    file_names: list[DocumentRequestBody]


class TitanCallbackRequest(BaseModel):
    documents: list[str]
