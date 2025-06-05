from pydantic import BaseModel

class ChatRequest(BaseModel):
    pair: str
    interval: str
    prompt: str
