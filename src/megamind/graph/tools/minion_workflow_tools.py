"""
Tools for searching business workflows and processes using Minion service.

This module provides workflow search tools that use Minion's /search/* APIs
instead of ZEP Cloud, offering a self-hosted semantic layer with richer
workflow knowledge capabilities via Neo4j.
"""

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
    logger.error(f"Minion workflow tool '{tool_name}' failed: {error}")
    return json.dumps(
        {
            "error": True,
            "message": f"Tool '{tool_name}' failed: {str(error)}",
            "suggestion": "The Minion service may be unavailable. Try using alternative tools or ask the user to check the service status.",
        },
        indent=2,
    )


# ==================== Workflow Search Tools ====================


@tool
async def search_business_workflows(query: str) -> str:
    """
    Search the business workflows knowledge graph for processes and procedures.

    Use this tool to find:
    - Business processes and their steps
    - Workflow definitions and transitions
    - Approval chains and state machines
    - End-to-end business flows

    This is a drop-in replacement for the ZEP-based workflow search,
    now using Minion's unified /search/search API with object_types filtering.

    Args:
        query: Concise search query (e.g., "sales order approval process")

    Returns:
        Matching workflow and process information from Neo4j knowledge graph.
    """
    try:
        client = _get_client()
        result = await client.search(
            query=query,
            object_types=["Workflow", "BusinessProcess", "ProcessStep"],
            limit=10,
        )
        return _format_result(result)
    except Exception as e:
        return _format_error("search_business_workflows", e)


@tool
async def search_workflow_knowledge(
    query: str, object_types: list[str] | None = None, limit: int = 10
) -> str:
    """
    Semantic search across the Neo4j knowledge graph for workflow-related knowledge.

    Use this tool for flexible knowledge searches where you want to control
    what types of objects to search. More powerful than search_business_workflows
    as it allows custom object type filtering.

    Args:
        query: Natural language search query
        object_types: Optional filter by types (e.g., ["Workflow", "Role", "Policy"])
        limit: Maximum results to return (default: 10)

    Returns:
        Search results with similarity scores from Neo4j graph.
    """
    try:
        client = _get_client()
        result = await client.search(
            query=query, object_types=object_types, limit=limit
        )
        return _format_result(result)
    except Exception as e:
        return _format_error("search_workflow_knowledge", e)


@tool
async def ask_workflow_question(question: str) -> str:
    """
    Ask a natural language question about workflows and business processes.

    Use this tool for direct questions that need synthesized answers from
    the knowledge graph, rather than just search results.

    Args:
        question: Natural language question (e.g., "What is the procurement workflow?")

    Returns:
        Natural language answer based on workflow knowledge.
    """
    try:
        client = _get_client()
        result = await client.ask(question)
        return _format_result(result)
    except Exception as e:
        return _format_error("ask_workflow_question", e)


@tool
async def get_workflow_related_objects(
    object_type: str, object_id: str, direction: str = "both", max_depth: int = 2
) -> str:
    """
    Find objects related to a workflow or process via graph traversal.

    Use this tool to discover connections between workflows, processes,
    roles, and other organizational elements. Useful for understanding
    relationships and dependencies in business processes.

    Args:
        object_type: Type of the source object (e.g., "Workflow", "BusinessProcess")
        object_id: ID of the source object (e.g., "Purchase Order Approval")
        direction: Traversal direction - "in", "out", or "both" (default: "both")
        max_depth: Maximum traversal depth (default: 2)

    Returns:
        Related objects with relationship details from the graph.
    """
    try:
        client = _get_client()
        result = await client.get_related(
            object_type=object_type,
            object_id=object_id,
            direction=direction,
            max_depth=max_depth,
        )
        return _format_result(result)
    except Exception as e:
        return _format_error("get_workflow_related_objects", e)


@tool
async def search_employees(query: str) -> str:
    """
    Search for employee and organizational information.

    Use this tool to find:
    - Employee information (name, role, department)
    - Company structure (departments, branches)
    - Reporting relationships
    - User roles and permissions

    This is a drop-in replacement for the ZEP-based employee search,
    now using Minion's unified /search/search API.

    Args:
        query: Concise search query (e.g., "finance department manager")

    Returns:
        Matching employee and organizational information from Neo4j.
    """
    try:
        client = _get_client()
        result = await client.search(
            query=query,
            object_types=["User", "Employee", "Department", "Role"],
            limit=10,
        )
        return _format_result(result)
    except Exception as e:
        return _format_error("search_employees", e)
