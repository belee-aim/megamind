from typing import Any, Dict, List, Literal, Optional, Union
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


class Policy(BaseModel):
    """Company policy information"""

    title: str = Field(description="Policy title")
    description: str = Field(description="Policy description")
    isCustom: bool = Field(description="Is the policy custom")
    category: Optional[Literal["essential", "industry"]] = Field(
        default=None, description="Policy category"
    )


class OfficeLocation(BaseModel):
    """Office location information"""

    name: str = Field(description="Location name")
    address_title: str = Field(description="Address title")
    address_line1: str = Field(description="Address line 1")
    city: str = Field(description="City")
    country: str = Field(description="Country")
    phone: str = Field(description="Phone number")
    employee_count: Optional[int] = Field(
        default=None, description="Number of employees at the location"
    )


class RetailStore(BaseModel):
    """Retail store information"""

    name: str = Field(description="Store name")
    store_name: str = Field(description="Store name")
    location: Optional[str] = Field(default=None, description="Location description")


class Department(BaseModel):
    """Department information"""

    name: str = Field(description="Department name")


class CompanyRole(BaseModel):
    """Company role/position information"""

    department: str = Field(description="Department name")
    role: str = Field(description="Role/position name")
    alias: str = Field(
        description="Role/position name but translated to English. (If role is in English, same as role)"
    )


class Employee(BaseModel):
    """Employee information"""

    role: str = Field(description="Employee's role/position")
    firstname: str = Field(description="Employee's first name")
    lastname: str = Field(description="Employee's last name")
    email: Optional[str] = Field(default=None, description="Employee's email address")
    reports_to: Optional[str] = Field(
        default=None,
        description="Name of person this employee reports to (infer from hierarchy if not explicit)",
    )
    gender: Optional[str] = Field(
        default=None,
        description="Gender of the employee (infer from name if not explicit)",
    )
    date_of_joining: Optional[str] = Field(
        default=None, description="Date of joining the company"
    )
    date_of_birth: Optional[str] = Field(
        default=None, description="Date of birth (infer from ID if not explicit)"
    )


class CompanyInformation(BaseModel):
    """
    Structured company information extracted from documents.
    All fields are optional - only extract if information is present in the documents.
    """

    company_profile: Optional[dict] = Field(
        default={},
        description="General company profile including name, industry, size, founding date, and overview. Return empty dict if not found.",
    )
    basic_information: Optional[dict] = Field(
        default={},
        description="Basic company information such as registration details, tax ID, headquarters address, contact information. Return empty dict if not found.",
    )
    mission: Optional[str] = Field(
        default=None, description="Company mission statement. Return null if not found."
    )
    vision: Optional[str] = Field(
        default=None, description="Company vision statement. Return null if not found."
    )
    company_policies: Optional[List[Policy]] = Field(
        default=[],
        description="List of company policies including HR policies, code of conduct, compliance policies, etc. Return empty list if not found.",
    )
    office_retail_locations: Optional[List[Union[OfficeLocation, RetailStore]]] = Field(
        default=[],
        description="List of office and retail locations with addresses, types, and operational details. Return empty list if not found.",
    )
    departments: Optional[List[Department]] = Field(
        default=[],
        description="List of unique departments in the organization. Return empty list if not found.",
    )
    company_roles: Optional[List[CompanyRole]] = Field(
        default=[],
        description="List of company roles/positions with department and role name. Return empty list if not found.",
    )
    employees: Optional[List[Employee]] = Field(
        default=[],
        description="List of employees with their role, name (split into firstname/lastname), email, and reporting structure. Return empty list if not found.",
    )
