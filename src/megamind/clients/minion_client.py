import httpx
from loguru import logger

from megamind.configuration import Configuration


class MinionClient:
    """
    A client for interacting with the Minion service.
    """

    def __init__(self, minion_api_url: str):
        """
        Initializes the Minion client.
        """
        self.api_url = minion_api_url
        logger.debug(f"Initializing Minion client with API URL: {self.api_url}")

    async def search_role_permissions(self, query: str):
        """
        Searches for role permissions in the Minion service.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/api/v1/graphiti/search",
                headers={"x-graph-name": "role"},
                json={"query": query},
            )
            response.raise_for_status()
            return response.json()
