import httpx
from loguru import logger


class MinionClient:
    """
    A client for interacting with the Minion service.
    Simplified to only provide document search functionality.
    """

    def __init__(self, minion_api_url: str):
        """
        Initializes the Minion client.
        """
        self.api_url = minion_api_url
        logger.debug(f"Initializing Minion client with API URL: {self.api_url}")

    async def search_document(self, query: str):
        """
        Searches for documents in the Minion service using graph-based search.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/api/v1/graphrag/search",
                json={"query": query},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()
