from typing import Annotated, Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator


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

    location_type: Literal["office"] = Field(
        default="office",
        description="Type of location (always 'office' for office locations)",
    )
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

    location_type: Literal["retail"] = Field(
        default="retail",
        description="Type of location (always 'retail' for retail stores)",
    )
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


class RawEmployee(BaseModel):
    """
    Raw employee information extracted directly from documents.
    Only includes explicitly stated information - no inference.
    """

    role: str = Field(description="Employee's role/position as stated in document")
    firstname: str = Field(description="Employee's first name")
    lastname: str = Field(description="Employee's last name")
    email: Optional[str] = Field(
        default=None,
        description="Employee's email address (only if explicitly stated)",
    )
    reports_to: Optional[str] = Field(
        default=None,
        description="Email of person this employee reports to (only if explicitly stated, do not infer)",
    )
    gender: Optional[str] = Field(
        default=None,
        description="Gender of the employee (only if explicitly stated)",
    )
    date_of_joining: Optional[str] = Field(
        default=None,
        description="Date of joining the company (only if explicitly stated)",
    )
    date_of_birth: Optional[str] = Field(
        default=None,
        description="Date of birth (only if explicitly stated)",
    )


class RawCompanyInformation(BaseModel):
    """
    Raw company information extracted directly from documents.
    Only includes explicitly stated information - no inference or enrichment.
    All fields are optional - only extract if information is explicitly present.
    """

    company_profile: Optional[dict] = Field(
        default={},
        description="General company profile including name, industry, size, founding date, and overview. Only extract if explicitly stated.",
    )
    basic_information: Optional[dict] = Field(
        default={},
        description="Basic company information such as registration details, tax ID, headquarters address, contact information. Only extract if explicitly stated.",
    )
    mission: Optional[str] = Field(
        default=None,
        description="Company mission statement. Only extract if explicitly stated.",
    )
    vision: Optional[str] = Field(
        default=None,
        description="Company vision statement. Only extract if explicitly stated.",
    )
    company_policies: Optional[List[Policy]] = Field(
        default=[],
        description="List of company policies. Only extract if explicitly stated.",
    )
    office_retail_locations: Optional[
        List[
            Annotated[
                Union[OfficeLocation, RetailStore], Field(discriminator="location_type")
            ]
        ]
    ] = Field(
        default=[],
        description="List of office and retail locations. Only extract if explicitly stated with location_type.",
    )
    departments: Optional[List[Department]] = Field(
        default=[],
        description="List of unique departments mentioned in documents. Only extract if explicitly stated.",
    )
    employees: Optional[List[RawEmployee]] = Field(
        default=[],
        description="List of employees with their basic information. Only extract explicitly stated information - no inference.",
    )

    @field_validator("office_retail_locations", mode="before")
    @classmethod
    def filter_empty_locations(cls, v):
        """Filter out empty dictionaries from office_retail_locations"""
        if isinstance(v, list):
            # Filter out empty dicts and dicts without required fields
            return [
                loc
                for loc in v
                if isinstance(loc, dict) and loc and "location_type" in loc
            ]
        return v


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
    office_retail_locations: Optional[
        List[
            Annotated[
                Union[OfficeLocation, RetailStore], Field(discriminator="location_type")
            ]
        ]
    ] = Field(
        default=[],
        description="List of office and retail locations with addresses, types, and operational details. Each location must have a 'location_type' field set to either 'office' or 'retail'. Return empty list if not found.",
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

    @field_validator("office_retail_locations", mode="before")
    @classmethod
    def filter_empty_locations(cls, v):
        """Filter out empty dictionaries from office_retail_locations"""
        if isinstance(v, list):
            # Filter out empty dicts and dicts without required fields
            return [
                loc
                for loc in v
                if isinstance(loc, dict) and loc and "location_type" in loc
            ]
        return v


class ProcessStepSchema(BaseModel):
    """Schema for a single process step in a process definition."""

    step_id: str = Field(description="Unique step identifier (e.g., 'verify_customer')")
    title: str = Field(description="Step title")
    description: str = Field(description="What to do in this step")
    action_type: str = Field(
        description="Type of action: validation, create_document, update_document, submit_document, workflow, search, etc."
    )
    target_doctype: Optional[str] = Field(
        default=None, description="Target DocType if applicable (e.g., 'Sales Order')"
    )
    mcp_tool_name: Optional[str] = Field(
        default=None,
        description="MCP tool used for this step (e.g., 'create_document', 'get_document', 'list_documents')",
    )


class KnowledgeEntrySchema(BaseModel):
    """Schema for extracted knowledge from conversations."""

    knowledge_type: Literal[
        "best_practice",
        "shortcut",
        "error_solution",
        "general_knowledge",
        "response_optimization",
    ] = Field(description="Type of knowledge being captured")
    title: str = Field(description="Clear, descriptive title")
    content: str = Field(description="Detailed content with context and explanation")
    summary: str = Field(description="One-sentence summary")
    possible_queries: List[str] = Field(
        default_factory=list,
        description="List of 3-5 possible search queries that would match this knowledge (different phrasings and question formats)",
    )
    doctype_name: Optional[str] = Field(
        default=None, description="Related ERPNext DocType (e.g., 'Sales Order')"
    )
    module: Optional[str] = Field(
        default=None, description="ERPNext module (e.g., 'Selling', 'Stock')"
    )
    category: Optional[str] = Field(
        default=None,
        description="Category for process definitions (e.g., 'Sales & Delivery')",
    )
    priority: int = Field(
        default=70, ge=1, le=100, description="Priority level (1-100)"
    )

    # Only for best_practice/shortcut (will be saved as process definitions):
    steps: Optional[Dict[str, ProcessStepSchema]] = Field(
        default=None, description="Process steps for best practices and shortcuts"
    )
    trigger_conditions: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Conditions that trigger this process (e.g., {'doctype': 'Sales Order', 'status': 'Draft'})",
    )
    prerequisites: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Prerequisites for executing this process (e.g., {'required_roles': ['Sales User']})",
    )

    # Only for response_optimization (performance improvement insights):
    original_metrics: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Original performance metrics (e.g., {'total_time_ms': 35000, 'tool_calls': 5, 'llm_latency_ms': 12000})",
    )
    optimization_approach: Optional[str] = Field(
        default=None,
        description="Detailed description of the optimized approach that would be faster",
    )
    estimated_improvement: Optional[str] = Field(
        default=None,
        description="Expected performance improvement (e.g., 'Reduce from 5 to 2 tool calls, saving ~20 seconds')",
    )

    # Search query optimization (when search_erpnext_knowledge was ineffective):
    ineffective_search_query: Optional[str] = Field(
        default=None,
        description="The original search query that didn't return useful results (e.g., 'search_erpnext_knowledge(\"payment entry\")')",
    )
    better_search_query: Optional[str] = Field(
        default=None,
        description='Improved search query with specific keywords and filters (e.g., \'search_erpnext_knowledge("Payment Entry required fields", doctype="Payment Entry")\')',
    )
    search_query_improvements: Optional[str] = Field(
        default=None,
        description="Explanation of what was wrong with original query and how the better query improves it",
    )


class KnowledgeExtractionResult(BaseModel):
    """Result of knowledge extraction from a conversation."""

    should_save: bool = Field(
        description="Whether the conversation contains valuable knowledge worth saving"
    )
    entries: List[KnowledgeEntrySchema] = Field(
        default_factory=list, description="List of extracted knowledge entries"
    )
