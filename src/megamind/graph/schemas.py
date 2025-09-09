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


class Permission(BaseModel):
    if_owner: str | None
    has_if_owner_enabled: bool
    select: int
    read: int
    write: int
    create: int
    delete: int
    submit: int
    cancel: int
    amend: int
    print: int
    email: int
    report: int
    import_perm: int = Field(alias="import")
    export: int
    share: int


class DoctypePermission(BaseModel):
    doctype: str
    permissions: Permission


class RoleGenerationResponse(BaseModel):
    """
    Response model for role generation requests.
    """

    roles: list[DoctypePermission] = Field(
        description="The generated roles based on the user's description."
    )


class RelatedRoleResponse(BaseModel):
    """
    Response model for finding a related role.
    """

    role_name: str = Field(description="The name of the related role.")
