from typing import Optional, List
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


# === ZEP MANAGEMENT REQUESTS ===


class ZepUserCreateRequest(BaseModel):
    user_id: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    metadata: Optional[dict] = None


class ZepUserUpdateRequest(BaseModel):
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    metadata: Optional[dict] = None


class ZepThreadCreateRequest(BaseModel):
    thread_id: str
    user_id: str
    metadata: Optional[dict] = None


class ZepThreadUpdateRequest(BaseModel):
    metadata: Optional[dict] = None


class ZepMessageAddRequest(BaseModel):
    thread_id: str
    messages: List[dict]  # List of {role, content, name?}


class ZepMemorySearchRequest(BaseModel):
    thread_id: str
    query: str
    limit: int = 5
