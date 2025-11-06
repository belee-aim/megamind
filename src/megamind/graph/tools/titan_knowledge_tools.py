"""
Tools for searching and retrieving ERPNext knowledge from Titan service.

These tools allow the LLM to dynamically search the knowledge base when needed,
rather than pre-loading context before every query.
"""

from typing import Optional
from langchain_core.tools import tool
from loguru import logger

from megamind.clients.titan_client import TitanClient


@tool
async def search_erpnext_knowledge(
    query: str,
    content_types: Optional[str] = None,
    doctype: Optional[str] = None,
    operation: Optional[str] = None,
    match_count: int = 5,
) -> str:
    """
    Search ERPNext knowledge base for relevant information about workflows, best practices, schemas, and examples.

    **CRITICAL: Use this tool BEFORE calling any MCP tools for ERPNext operations!**

    **When to use this tool:**

    **MANDATORY (ALWAYS USE BEFORE):**
    - **BEFORE calling ANY MCP tool for ERPNext** (create, update, delete, workflow actions)
    - **BEFORE creating or updating any DocType** - search for required fields and workflows
    - **BEFORE performing workflow operations** (submit, cancel, amend) - understand sequence
    - **BEFORE complex operations** - validate your approach with documented workflows

    **Also use for:**
    - User asks about ERPNext workflows or processes (e.g., "How do I create a Sales Order?")
    - User needs information about DocType fields or schemas (e.g., "What fields does Payment Entry have?")
    - User requests best practices (e.g., "Best way to handle stock reconciliation?")
    - User wants examples of operations (e.g., "Show me an example of a Purchase Order")
    - Troubleshooting errors or issues (e.g., "Why am I getting validation error X?")

    **Parameters:**
    - query: Natural language search query describing what you need
    - content_types: Optional comma-separated list to filter by type. Options: workflow, best_practice, schema, example, error_pattern, relationship, process
    - doctype: Optional DocType name to filter results (e.g., "Sales Order", "Payment Entry")
    - operation: Optional operation type to filter. Options: create, read, update, delete, workflow, search
    - match_count: Number of results to return (default: 5, max recommended: 10)

    **Examples:**

    **Before operations (MANDATORY pattern):**
    - search_erpnext_knowledge("Sales Order required fields create workflow", content_types="schema,workflow", doctype="Sales Order")
    - search_erpnext_knowledge("Payment Entry required fields and validation", content_types="schema,best_practice", doctype="Payment Entry")
    - search_erpnext_knowledge("submit Purchase Invoice workflow steps", content_types="workflow", doctype="Purchase Invoice")

    **For user questions:**
    - search_erpnext_knowledge("How to create sales order", content_types="workflow", doctype="Sales Order")
    - search_erpnext_knowledge("Stock reconciliation process", content_types="workflow,example")
    - search_erpnext_knowledge("Fixing 'Insufficient stock' error", content_types="error_pattern")

    **Returns:**
    Formatted knowledge entries with titles, types, relevance scores, and full content.

    **IMPORTANT:** Review the returned schemas and workflows carefully before calling MCP tools.
    Do NOT skip this step - it prevents errors and ensures successful operations.
    """
    logger.info(f"Tool called: search_erpnext_knowledge(query='{query[:50]}...', content_types={content_types}, doctype={doctype})")

    try:
        # Create Titan client
        titan_client = TitanClient()

        # Parse content_types if provided
        types_list = None
        if content_types:
            types_list = [t.strip() for t in content_types.split(",")]
            logger.debug(f"Filtering by content types: {types_list}")

        # Search knowledge
        results = await titan_client.search_knowledge(
            query=query,
            content_types=types_list,
            doctype_filter=doctype,
            operation_filter=operation,
            match_count=match_count,
            similarity_threshold=0.7,
        )

        if not results:
            logger.info("No knowledge entries found")
            return "No relevant knowledge found in the ERPNext knowledge base for this query. You may need to rely on your general ERPNext knowledge or ask the user for more specific information."

        # Format results for LLM consumption
        formatted_parts = [f"# ERPNext Knowledge Search Results ({len(results)} entries found)\n"]

        for i, entry in enumerate(results, 1):
            title = entry.get("title", "Untitled")
            content_type = entry.get("content_type", "general")
            content = entry.get("content", "")
            summary = entry.get("summary", "")
            similarity = entry.get("similarity", 0)
            doctype_name = entry.get("doctype_name", "")
            operation_type = entry.get("operation_type", "")

            # Build entry header
            formatted_parts.append(f"## {i}. {title}")
            formatted_parts.append(f"**Type**: {content_type.replace('_', ' ').title()}")

            if doctype_name:
                formatted_parts.append(f"**DocType**: {doctype_name}")
            if operation_type:
                formatted_parts.append(f"**Operation**: {operation_type.title()}")

            formatted_parts.append(f"**Relevance**: {similarity:.0%}\n")

            if summary:
                formatted_parts.append(f"**Summary**: {summary}\n")

            # Add content (truncate if very long to save tokens)
            if len(content) > 3000:
                content = content[:3000] + "\n\n[Content truncated for brevity...]"

            formatted_parts.append(content)
            formatted_parts.append("\n---\n")

        result_text = "\n".join(formatted_parts)
        logger.info(f"Returning {len(results)} formatted knowledge entries ({len(result_text)} chars)")

        return result_text

    except Exception as e:
        logger.error(f"Error in search_erpnext_knowledge tool: {e}")
        return f"Error searching knowledge base: {str(e)}. Continue with your general ERPNext knowledge."


@tool
async def get_erpnext_knowledge_by_id(knowledge_id: int) -> str:
    """
    Retrieve a specific ERPNext knowledge entry by its ID.

    Use this when you've seen a reference to a specific knowledge entry ID
    and want to get its full content.

    **Parameters:**
    - knowledge_id: The numeric ID of the knowledge entry

    **Returns:**
    Full knowledge entry with all details.
    """
    logger.info(f"Tool called: get_erpnext_knowledge_by_id(knowledge_id={knowledge_id})")

    try:
        titan_client = TitanClient()
        entry = await titan_client.get_knowledge_by_id(knowledge_id)

        if not entry:
            return f"Knowledge entry with ID {knowledge_id} not found."

        # Format entry
        formatted = [
            f"# {entry.get('title', 'Untitled')}",
            f"\n**Type**: {entry.get('content_type', 'general').replace('_', ' ').title()}",
        ]

        if entry.get("doctype_name"):
            formatted.append(f"**DocType**: {entry['doctype_name']}")
        if entry.get("operation_type"):
            formatted.append(f"**Operation**: {entry['operation_type'].title()}")
        if entry.get("module"):
            formatted.append(f"**Module**: {entry['module']}")

        formatted.append("\n")

        if entry.get("summary"):
            formatted.append(f"**Summary**: {entry['summary']}\n")

        formatted.append(entry.get("content", ""))

        return "\n".join(formatted)

    except Exception as e:
        logger.error(f"Error in get_erpnext_knowledge_by_id tool: {e}")
        return f"Error retrieving knowledge entry {knowledge_id}: {str(e)}"
