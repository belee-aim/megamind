import json

from langchain_core.tools import tool
from loguru import logger

from megamind.clients.minion_client import MinionClient
from megamind.utils.config import settings


def _get_client() -> MinionClient:
    """Get a configured MinionClient instance."""
    return MinionClient(settings.minion_api_url)


def _format_result(result: dict) -> str:
    """Format API result as JSON string."""
    return json.dumps(result, indent=2, ensure_ascii=False)


def _format_error(tool_name: str, error: Exception) -> str:
    """Format error message for tool failures."""
    logger.error(f"Minion tool '{tool_name}' failed: {error}")
    return json.dumps({
        "error": True,
        "message": f"Tool '{tool_name}' failed: {str(error)}",
        "suggestion": "The Minion service may be unavailable. Try using alternative tools or ask the user to check the service status."
    }, indent=2)


# ==================== Search Tools ====================


@tool
async def search_document(query: str) -> str:
    """
    Search for documents in the Document Management System (DMS) using GraphRAG.

    Use this tool to find uploaded documents, files, and records
    that match a natural language query.

    Args:
        query: Natural language search query

    Returns:
        Matching documents with answer and sources
    """
    try:
        client = _get_client()
        result = await client.search_document(query)
        return _format_result(result)
    except Exception as e:
        return _format_error("search_document", e)


@tool
async def semantic_search(
    query: str,
    labels: list[str] | None = None,
    limit: int = 10,
) -> str:
    """
    Search across synced ERPNext documents using vector similarity.

    Use this tool to find documents (Purchase Orders, Sales Orders, Invoices, etc.)
    that semantically match your query. Great for finding related transactions,
    similar documents, or answering questions about specific records.

    Args:
        query: Natural language search query (e.g., "pending invoices for ABC Corp")
        labels: Optional filter by document types (e.g., ["PurchaseOrder", "SalesOrder"])
        limit: Maximum results to return (default: 10)

    Returns:
        Matching documents with similarity scores
    """
    try:
        client = _get_client()
        result = await client.semantic_search(query, labels=labels, limit=limit)
        return _format_result(result)
    except Exception as e:
        return _format_error("semantic_search", e)


@tool
async def graph_search(
    query: str,
    object_types: list[str] | None = None,
    limit: int = 10,
) -> str:
    """
    Semantic search across the Neo4j knowledge graph.

    Use this tool to find processes, workflows, roles, policies, and other
    organizational knowledge. Best for finding business process information.

    Args:
        query: Natural language search query
        object_types: Filter by types (e.g., ["process", "workflow", "role"])
        limit: Maximum results to return

    Returns:
        Search results with similarity scores
    """
    try:
        client = _get_client()
        result = await client.search(query, object_types=object_types, limit=limit)
        return _format_result(result)
    except Exception as e:
        return _format_error("graph_search", e)


@tool
async def ask_knowledge_graph(question: str) -> str:
    """
    Ask a natural language question to the knowledge graph.

    Use this tool for direct questions about the organization, processes,
    workflows, or any knowledge stored in the graph database.

    Args:
        question: Natural language question (e.g., "What is the approval process for purchase orders?")

    Returns:
        Natural language answer based on graph knowledge
    """
    try:
        client = _get_client()
        result = await client.ask(question)
        return _format_result(result)
    except Exception as e:
        return _format_error("ask_knowledge_graph", e)


# ==================== Document Context Tools ====================


@tool
async def get_document_chain(doctype: str, name: str) -> str:
    """
    Get the transaction chain for a document showing related upstream/downstream documents.

    Use this tool to understand the full lifecycle of a transaction:
    - Sales Order → Delivery Note → Sales Invoice
    - Purchase Order → Purchase Receipt → Purchase Invoice
    - Material Request → Purchase Order → Purchase Receipt

    Args:
        doctype: Document type (e.g., "Sales Order", "Purchase Order")
        name: Document name/ID (e.g., "SO-00123", "PO-00456")

    Returns:
        Document chain with all related transactions
    """
    try:
        client = _get_client()
        result = await client.get_chain(doctype, name)
        return _format_result(result)
    except Exception as e:
        return _format_error("get_document_chain", e)


@tool
async def get_related_documents(
    object_type: str,
    object_id: str,
    direction: str = "both",
    max_depth: int = 2,
) -> str:
    """
    Find objects related to a given document via graph traversal.

    Use this tool to discover connections between documents, entities, and processes.
    Useful for understanding relationships and dependencies.

    Args:
        object_type: Type of the source object (e.g., "Purchase Order", "Customer")
        object_id: ID of the source object (e.g., "PO-001", "CUST-001")
        direction: Traversal direction - "in", "out", or "both" (default: "both")
        max_depth: Maximum traversal depth (default: 2)

    Returns:
        Related objects with relationship details
    """
    try:
        client = _get_client()
        result = await client.get_related(
            object_type, object_id, direction=direction, max_depth=max_depth
        )
        return _format_result(result)
    except Exception as e:
        return _format_error("get_related_documents", e)


@tool
async def get_document_context(doctype: str, name: str) -> str:
    """
    Get full context for a document including chain, owner, items, and workflow state.

    Use this tool when you need comprehensive information about a specific document
    before taking action or answering questions about it.

    Args:
        doctype: Document type (e.g., "Sales Order", "Purchase Invoice")
        name: Document name/ID (e.g., "SO-00123")

    Returns:
        Document details with owner, items, workflow state, and related context
    """
    try:
        client = _get_client()
        result = await client.get_document_context(doctype, name)
        return _format_result(result)
    except Exception as e:
        return _format_error("get_document_context", e)


# ==================== Entity Context Tools ====================


@tool
async def get_user_context(email: str) -> str:
    """
    Get context for a user including roles, pending approvals, and recent documents.

    Use this tool to understand what a user can do, what's pending for them,
    and their recent activity. Essential for authorization checks.

    Args:
        email: User email address

    Returns:
        User profile with roles, pending approvals, and recent documents
    """
    try:
        client = _get_client()
        result = await client.get_user_context(email)
        return _format_result(result)
    except Exception as e:
        return _format_error("get_user_context", e)


@tool
async def get_entity_context(entity_type: str, entity_id: str) -> str:
    """
    Get context for a business entity (Customer, Supplier, Item, etc.).

    Use this tool to get comprehensive information about an entity including
    related transactions, statistics, and history.

    Args:
        entity_type: Entity type (e.g., "Customer", "Supplier", "Item")
        entity_id: Entity ID (e.g., "CUST-001", "SUP-001", "ITEM-001")

    Returns:
        Entity details with related transactions and statistics
    """
    try:
        client = _get_client()
        result = await client.get_entity_context(entity_type, entity_id)
        return _format_result(result)
    except Exception as e:
        return _format_error("get_entity_context", e)


# ==================== Analytics Tools ====================


@tool
async def aggregate_data(
    object_type: str,
    group_by: str,
    metric: str = "count",
    metric_field: str | None = None,
    filters: dict | None = None,
) -> str:
    """
    Aggregate data by dimensions for business intelligence queries.

    Use this tool for analytical questions like:
    - "How many purchase orders per supplier?"
    - "Total sales amount by customer"
    - "Average invoice amount by month"

    Args:
        object_type: Type to aggregate (e.g., "Purchase Order", "Sales Invoice")
        group_by: Field to group by (e.g., "supplier", "customer", "status")
        metric: Aggregation metric - "count", "sum", "avg", "min", "max"
        metric_field: Field for sum/avg/min/max metrics (e.g., "grand_total")
        filters: Optional filters (e.g., {"status": "completed"})

    Returns:
        Aggregated results grouped by the specified dimension
    """
    try:
        client = _get_client()
        result = await client.aggregate(
            object_type,
            group_by,
            metric=metric,
            metric_field=metric_field,
            filters=filters,
        )
        return _format_result(result)
    except Exception as e:
        return _format_error("aggregate_data", e)
