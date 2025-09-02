from typing import Any
from pydantic import BaseModel


class MainResponse(BaseModel):
    message: str = "Success"
    error: str | None = None
    response: Any | None = None
