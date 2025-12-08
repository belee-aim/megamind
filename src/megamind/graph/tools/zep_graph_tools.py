"""
Tools for searching Zep knowledge graphs.

These tools allow the LLM to search business workflows, employee information,
and user-specific knowledge stored in Zep's graph database.
"""

from langchain_core.tools import tool
from loguru import logger

from megamind.clients.zep_client import get_zep_client


@tool
async def search_business_workflows(
    query: str,
    scope: str = "edges",
    limit: int = 10,
) -> str:
    """
    Search the business workflows knowledge graph for processes, workflows, and procedures.

    Use this tool to find:
    - Business processes and their steps
    - Workflow definitions and transitions
    - Approval chains and state machines
    - End-to-end business flows (e.g., Lead → Opportunity → Quotation → Sales Order)

    Args:
        query: Natural language search query (e.g., "sales order approval process")
        scope: What to search - "edges" (relationships/facts) or "nodes" (entities)
        limit: Maximum results to return (default: 10)

    Returns:
        Matching workflow and process information from the knowledge graph.
    """
    logger.info(
        f"Tool called: search_business_workflows(query='{query[:50]}...', scope={scope})"
    )

    try:
        zep_client = get_zep_client()

        if not zep_client.is_available():
            return "Zep client not available. Unable to search business workflows."

        results = await zep_client.search_graph(
            user_id="business_workflows_json",
            query=query,
            scope=scope,
            limit=limit,
        )

        if not results:
            return f"No business workflow information found for: {query}"

        # Format results for LLM consumption
        formatted_parts = [
            f"# Business Workflow Search Results ({len(results)} found)\n"
        ]

        for i, item in enumerate(results, 1):
            if scope == "edges":
                # Edge format: fact/relationship
                fact = item.get("fact", "")
                source = item.get("source_node_name", "")
                target = item.get("target_node_name", "")
                formatted_parts.append(f"## {i}. {source} → {target}")
                formatted_parts.append(f"{fact}\n")
            else:
                # Node format: entity
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
        logger.error(f"Error in search_business_workflows: {e}")
        return f"Error searching business workflows: {str(e)}"


@tool
async def search_employees(
    query: str,
    scope: str = "nodes",
    limit: int = 10,
) -> str:
    """
    Search the employees knowledge graph for organizational information.

    Use this tool to find:
    - Employee information (name, role, department)
    - Company structure (departments, branches)
    - Reporting relationships
    - Contact information

    Args:
        query: Natural language search query (e.g., "finance department manager")
        scope: What to search - "nodes" (entities) or "edges" (relationships)
        limit: Maximum results to return (default: 10)

    Returns:
        Matching employee and organizational information.
    """
    logger.info(
        f"Tool called: search_employees(query='{query[:50]}...', scope={scope})"
    )

    try:
        zep_client = get_zep_client()

        if not zep_client.is_available():
            return "Zep client not available. Unable to search employees."

        results = await zep_client.search_graph(
            user_id="employees",
            query=query,
            scope=scope,
            limit=limit,
        )

        if not results:
            return f"No employee information found for: {query}"

        # Format results
        formatted_parts = [f"# Employee Search Results ({len(results)} found)\n"]

        for i, item in enumerate(results, 1):
            if scope == "nodes":
                name = item.get("name", "Unknown")
                labels = item.get("labels", [])
                summary = item.get("summary", "")
                formatted_parts.append(f"## {i}. {name}")
                if labels:
                    formatted_parts.append(f"**Type**: {', '.join(labels)}")
                if summary:
                    formatted_parts.append(f"{summary}\n")
            else:
                fact = item.get("fact", "")
                source = item.get("source_node_name", "")
                target = item.get("target_node_name", "")
                formatted_parts.append(f"## {i}. {source} → {target}")
                formatted_parts.append(f"{fact}\n")

        return "\n".join(formatted_parts)

    except Exception as e:
        logger.error(f"Error in search_employees: {e}")
        return f"Error searching employees: {str(e)}"


@tool
async def search_user_knowledge(
    query: str,
    user_email: str,
    scope: str = "edges",
    limit: int = 10,
) -> str:
    """
    Search a specific user's personal knowledge graph.

    Use this tool to find:
    - User's accumulated context and preferences
    - Past interactions and decisions
    - User-specific information stored over time

    Args:
        query: Natural language search query
        user_email: The user's email address (used as graph_id)
        scope: What to search - "edges" (facts) or "nodes" (entities)
        limit: Maximum results to return (default: 10)

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
            user_id=user_email,
            query=query,
            scope=scope,
            limit=limit,
        )

        if not results:
            return f"No personal knowledge found for query: {query}"

        # Format results
        formatted_parts = [f"# User Knowledge Search Results ({len(results)} found)\n"]

        for i, item in enumerate(results, 1):
            if scope == "edges":
                fact = item.get("fact", "")
                formatted_parts.append(f"{i}. {fact}")
            else:
                name = item.get("name", "Unknown")
                summary = item.get("summary", "")
                formatted_parts.append(f"{i}. **{name}**: {summary}")

        return "\n".join(formatted_parts)

    except Exception as e:
        logger.error(f"Error in search_user_knowledge: {e}")
        return f"Error searching user knowledge: {str(e)}"
