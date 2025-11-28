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
    doctype: Optional[str] = None,
    match_count: int = 5,
) -> str:
    """
    Search ERPNext knowledge base for relevant information about workflows, best practices, schemas, examples, and optimization patterns.

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
    - **Learning from past inefficiencies** - search for optimization patterns to improve response speed

    **Parameters:**
    - query: Natural language search query describing what you need
    - doctype: Optional DocType name to filter results (e.g., "Sales Order", "Payment Entry")
    - match_count: Number of results to return (default: 5, max recommended: 10)

    **Examples:**

    **Before operations (MANDATORY pattern):**
    - search_erpnext_knowledge("Sales Order required fields create workflow", doctype="Sales Order")
    - search_erpnext_knowledge("Payment Entry required fields and validation", doctype="Payment Entry")
    - search_erpnext_knowledge("submit Purchase Invoice workflow steps", doctype="Purchase Invoice")

    **For user questions:**
    - search_erpnext_knowledge("How to create sales order", doctype="Sales Order")
    - search_erpnext_knowledge("Stock reconciliation process")
    - search_erpnext_knowledge("Fixing 'Insufficient stock' error")

    **For optimization patterns (learn from past slow responses):**
    - search_erpnext_knowledge("optimization create sales order")
    - search_erpnext_knowledge("improve search query payment entry")
    - search_erpnext_knowledge("faster approach stock entry")
    - search_erpnext_knowledge("reduce tool calls sales order")

    **Returns:**
    Formatted knowledge entries with titles, relevance scores, and full content. May include optimization patterns with search query improvements and performance tips.

    **IMPORTANT:** Review the returned schemas and workflows carefully before calling MCP tools.
    Do NOT skip this step - it prevents errors and ensures successful operations.
    """
    logger.info(f"Tool called: search_erpnext_knowledge(query='{query[:50]}...', doctype={doctype})")

    try:
        # Create Titan client
        titan_client = TitanClient()

        # Search knowledge
        results = await titan_client.search_knowledge(
            query=query,
            doctype_filter=doctype,
            match_count=match_count,
            similarity_threshold=0.7,
        )

        if not results:
            logger.info("No knowledge entries found")
            return "No relevant knowledge found in the knowledge base for this query. You may need to rely on your general knowledge or ask the user for more specific information."

        # Format results for LLM consumption
        formatted_parts = [f"# Knowledge Search Results ({len(results)} entries found)\n"]

        for i, entry in enumerate(results, 1):
            title = entry.get("title", "Untitled")
            content = entry.get("content", "")
            summary = entry.get("summary", "")
            similarity = entry.get("similarity", 0)
            doctype_name = entry.get("doctype_name", "")
            meta_data = entry.get("meta_data", {})

            # Build entry header
            formatted_parts.append(f"## {i}. {title}")

            if doctype_name:
                formatted_parts.append(f"**DocType**: {doctype_name}")

            formatted_parts.append(f"**Relevance**: {similarity:.0%}\n")

            # CRITICAL: Include meta_data so LLM can see is_widget marker
            if meta_data:
                is_widget = meta_data.get("is_widget", False)
                if is_widget:
                    formatted_parts.append(f"**🎯 WIDGET KNOWLEDGE - RETURN IMMEDIATELY**: This is a widget response. Return the content below directly without any additional processing or tool calls.\n")
                    formatted_parts.append(f"**Widget Type**: {meta_data.get('widget_type', 'unknown')}\n")
                    if meta_data.get("has_filters"):
                        formatted_parts.append(f"**Has Filters**: Yes - Extract filter values from user query\n")

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
        return f"Error searching knowledge base: {str(e)}. Continue with your general knowledge."


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
        ]

        if entry.get("doctype_name"):
            formatted.append(f"\n**DocType**: {entry['doctype_name']}")
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


