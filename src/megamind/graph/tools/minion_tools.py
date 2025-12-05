from langchain_core.tools import tool
from megamind.clients.minion_client import MinionClient
from megamind.utils.config import settings


@tool
async def search_document(query: str) -> str:
    """
    Search for documents using graph-based search.

    Use this when you need to find documents, records, or entities
    that match a natural language query.

    Args:
        query: Natural language search query

    Returns:
        Matching documents ranked by relevance
    """
    client = MinionClient(settings.minion_api_url)
    result = await client.search_document(query)
    return str(result)
