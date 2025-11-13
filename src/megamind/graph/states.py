from typing import List, Annotated, TypedDict, Dict, Any
from langgraph.graph.message import add_messages
from langchain_core.messages.utils import AnyMessage


class AgentState(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]
    access_token: str | None
    user_consent_response: str | None

    # Enhanced stock movement agent state fields
    validation_context: Dict[str, Any] | None
    workflow_state: Dict[str, Any] | None
    performance_metrics: Dict[str, Any] | None

    # CRAG (Corrective RAG) state fields
    correction_attempts: int | None
    last_error_context: Dict[str, Any] | None
    is_correction_mode: bool | None


class StockMovementState(TypedDict):
    """
    Enhanced state specifically for stock movement operations.
    Includes all the enhanced features from the improvement plan.
    """

    # Core state fields
    messages: Annotated[List[AnyMessage], add_messages]
    company: str
    last_stock_entry_id: str | None

    # Enhanced search and validation
    recent_search_results: List[Dict[str, Any]] | None
    validation_context: Dict[str, Any] | None
    search_metadata: Dict[str, Any] | None

    # Workflow and permissions
    workflow_state: Dict[str, Any] | None
    field_permissions: Dict[str, Any] | None
    document_status: Dict[str, Any] | None

    # Performance and analytics
    performance_metrics: Dict[str, Any] | None
    analytics_context: Dict[str, Any] | None
    cache_info: Dict[str, Any] | None

    # User experience enhancements
    contextual_help: Dict[str, Any] | None
    error_context: Dict[str, Any] | None
    suggestions: List[Dict[str, Any]] | None

    # Business intelligence
    transfer_patterns: List[Dict[str, Any]] | None
    predictive_insights: Dict[str, Any] | None
    optimization_recommendations: List[Dict[str, Any]] | None


class RoleGenerationState(TypedDict):
    access_token: str
    role_name: str
    user_description: str
    generated_roles: Dict[str, Any] | None
    permission_description: str | None
    existing_roles: list[str] | None
    related_role: str | None
    related_role_permissions: Dict[str, Any] | None
