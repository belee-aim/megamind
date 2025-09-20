from langchain_core.tools import tool
from megamind.clients.minion_client import MinionClient
from megamind.utils.config import settings


@tool
async def search_role_permissions(query: str):
    """
    Searches for role permissions in the Minion service.
    """
    client = MinionClient(settings.minion_api_url)
    return await client.search_role_permissions(query)
