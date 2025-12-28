"""
Tools for document search using the Minion service.

The Minion service provides semantic/graph-based search over documents
in the Document Management System (DMS).
"""

import json

import httpx
from langchain_core.tools import tool
from loguru import logger

from megamind.clients.minion_client import get_minion_client


@tool
async def search_document(
    query: str,
    limit: int = 10,
) -> str:
    """
    Search for documents uploaded in the system's Document Management System (DMS) using graph-based search.

    This tool uses semantic search powered by GraphRAG to find documents that match
    the natural language query. It understands context and relationships between
    documents for more intelligent retrieval.

    Use this tool when you need to:
    - Find documents, files, or records in the DMS
    - Search for policies, procedures, or guidelines
    - Locate contracts, agreements, or legal documents
    - Find reports, presentations, or other business documents

    Args:
        query: Natural language search query describing what you're looking for.
               Be specific for better results (e.g., "Q4 2024 sales report" instead of "report")
        limit: Maximum number of results to return (default: 10, max: 50)

    Returns:
        JSON string containing matching documents ranked by relevance.
        Each result includes document metadata and relevance score.

    Examples:
        - search_document("employee handbook policies")
        - search_document("sales contract template", limit=5)
        - search_document("quarterly financial report Q4 2024")
    """
    try:
        # Validate limit
        if limit < 1:
            limit = 1
        elif limit > 50:
            limit = 50

        # Use singleton client for efficient connection reuse
        client = get_minion_client()
        result = await client.search_document(
            query=query,
            limit=limit,
        )

        # Format result as structured JSON
        if isinstance(result, dict):
            return json.dumps(result, indent=2, ensure_ascii=False)
        elif isinstance(result, list):
            return json.dumps(
                {
                    "query": query,
                    "count": len(result),
                    "results": result,
                },
                indent=2,
                ensure_ascii=False,
            )
        else:
            return str(result)

    except httpx.HTTPStatusError as e:
        logger.error(f"Minion API error: {e.response.status_code}")
        return json.dumps(
            {
                "error": f"API error: {e.response.status_code}",
                "query": query,
                "message": "The document search service returned an error. Please try again.",
            }
        )
    except httpx.RequestError as e:
        logger.error(f"Minion connection error: {e}")
        return json.dumps(
            {
                "error": "Connection error",
                "query": query,
                "message": "Could not connect to the document search service. Please try again later.",
            }
        )
    except Exception as e:
        logger.error(f"Document search failed: {e}")
        return json.dumps(
            {
                "error": str(e),
                "query": query,
                "message": "Failed to search documents. Please try again or refine your query.",
            }
        )
