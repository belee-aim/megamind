"""
Tools for searching Zep knowledge graphs.
Optimized for performance - uses minimal parameters.
See: https://help.getzep.com/performance
"""

from langchain_core.tools import tool
from loguru import logger

from megamind.clients.zep_client import get_zep_client


@tool
async def search_business_workflows(query: str) -> str:
    """
    Search the business workflows knowledge graph for processes and procedures.

    Use this tool to find:
    - Business processes and their steps
    - Workflow definitions and transitions
    - Approval chains and state machines
    - End-to-end business flows

    Args:
        query: Concise search query (e.g., "sales order approval process")

    Returns:
        Matching workflow and process information.
    """
    logger.info(f"Tool called: search_business_workflows(query='{query[:50]}...')")

    try:
        zep_client = get_zep_client()

        if not zep_client.is_available():
            return "Zep client not available. Unable to search business workflows."

        results = await zep_client.search_graph(
            query=query,
            graph_id="business_workflows_json",
        )

        if not results:
            return f"No business workflow information found for: {query}"

        # Format results for LLM consumption
        formatted_parts = [
            f"# Business Workflow Search Results ({len(results)} found)\n"
        ]

        for i, item in enumerate(results, 1):
            fact = item.get("fact", "")
            source = item.get("source_node_name", "")
            target = item.get("target_node_name", "")
            formatted_parts.append(f"## {i}. {source} → {target}")
            formatted_parts.append(f"{fact}\n")

        return "\n".join(formatted_parts)

    except Exception as e:
        logger.error(f"Error in search_business_workflows: {e}")
        return f"Error searching business workflows: {str(e)}"


@tool
async def search_employees(query: str) -> str:
    """
    Search the employees knowledge graph for organizational information.

    Use this tool to find:
    - Employee information (name, role, department)
    - Company structure (departments, branches)
    - Reporting relationships

    Args:
        query: Concise search query (e.g., "finance department manager")

    Returns:
        Matching employee and organizational information.
    """
    logger.info(f"Tool called: search_employees(query='{query[:50]}...')")

    try:
        zep_client = get_zep_client()

        if not zep_client.is_available():
            return "Zep client not available. Unable to search employees."

        results = await zep_client.search_graph(
            query=query,
            graph_id="employees",
        )

        if not results:
            return f"No employee information found for: {query}"

        # Format results
        formatted_parts = [f"# Employee Search Results ({len(results)} found)\n"]

        for i, item in enumerate(results, 1):
            name = item.get("name", "Unknown")
            labels = item.get("labels", [])
            summary = item.get("summary", "")
            formatted_parts.append(f"## {i}. {name}")
            if labels:
                formatted_parts.append(f"**Type**: {', '.join(labels)}")
            if summary:
                formatted_parts.append(f"{summary}\n")

        return "\n".join(formatted_parts)

    except Exception as e:
        logger.error(f"Error in search_employees: {e}")
        return f"Error searching employees: {str(e)}"


@tool
async def search_user_knowledge(query: str, user_email: str) -> str:
    """
    Search a specific user's personal knowledge graph.

    Use this tool to find:
    - User's accumulated context and preferences
    - Past interactions and decisions
    - User-specific information stored over time

    Args:
        query: Concise search query
        user_email: The user's email address

    Returns:
        Matching information from the user's personal knowledge graph.
    """
    logger.info(
        f"Tool called: search_user_knowledge(query='{query[:50]}...', user={user_email})"
    )

    try:
        zep_client = get_zep_client()

        if not zep_client.is_available():
            return "Zep client not available. Unable to search user knowledge."

        results = await zep_client.search_graph(
            query=query,
            user_id=user_email,
        )

        if not results:
            return f"No personal knowledge found for query: {query}"

        # Format results
        formatted_parts = [f"# User Knowledge Search Results ({len(results)} found)\n"]

        for i, item in enumerate(results, 1):
            fact = item.get("fact", "")
            formatted_parts.append(f"{i}. {fact}")

        return "\n".join(formatted_parts)

    except Exception as e:
        logger.error(f"Error in search_user_knowledge: {e}")
        return f"Error searching user knowledge: {str(e)}"
