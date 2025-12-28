"""
Minion client for document search using semantic/graph-based search.

The Minion service provides semantic search over documents in the DMS,
using graph-based RAG (GraphRAG) for intelligent document retrieval.
"""

from typing import Any, Optional

import httpx
from loguru import logger

from megamind.utils.config import settings


class MinionClient:
    """
    Client for interacting with the Minion document search service.

    Features:
    - Connection pooling via shared httpx.AsyncClient
    - Multi-tenant support via x-tenant-id header
    - Authorization passthrough for authenticated requests
    - Configurable timeouts and retry behavior

    Usage:
        # Get the singleton client
        client = get_minion_client()

        # Search documents (unauthenticated)
        results = await client.search_document("sales report Q4")

        # Search documents (authenticated)
        results = await client.search_document(
            "sales report Q4",
            access_token="user_jwt_token"
        )
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        tenant_id: Optional[str] = None,
        timeout: float = 30.0,
    ):
        """
        Initialize the Minion client.

        Args:
            api_url: Base URL for the Minion API (defaults to settings.minion_api_url)
            tenant_id: Tenant identifier for multi-tenancy (defaults to settings.tenant_id)
            timeout: Request timeout in seconds (default: 30.0)
        """
        self.api_url = api_url or settings.minion_api_url
        self.tenant_id = tenant_id or settings.tenant_id
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

        logger.debug(
            f"MinionClient initialized: url={self.api_url}, tenant={self.tenant_id}"
        )

    async def _get_client(self) -> httpx.AsyncClient:
        """
        Get or create the shared httpx.AsyncClient with connection pooling.

        Returns:
            Configured httpx.AsyncClient instance
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                limits=httpx.Limits(
                    max_keepalive_connections=5,
                    max_connections=10,
                    keepalive_expiry=30.0,
                ),
            )
            logger.debug("Created new httpx.AsyncClient for MinionClient")
        return self._client

    def _build_headers(self, access_token: Optional[str] = None) -> dict[str, str]:
        """
        Build request headers with tenant ID and optional authorization.

        Args:
            access_token: Optional Bearer token for authenticated requests

        Returns:
            Dictionary of HTTP headers
        """
        headers = {
            "Content-Type": "application/json",
            "x-tenant-id": self.tenant_id,
        }

        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        return headers

    async def search_document(
        self,
        query: str,
        access_token: Optional[str] = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """
        Search for documents using graph-based semantic search.

        This method queries the Minion service's GraphRAG endpoint to find
        relevant documents based on natural language queries.

        Args:
            query: Natural language search query
            access_token: Optional Bearer token for authenticated requests
            limit: Maximum number of results to return (default: 10)

        Returns:
            Dictionary containing search results with the following structure:
            {
                "results": [...],  # List of matching documents
                "query": str,      # Original query
                "count": int       # Number of results
            }

        Raises:
            httpx.HTTPStatusError: If the API returns an error status
            httpx.RequestError: If there's a network error
        """
        logger.debug(f"Searching documents: query='{query[:50]}...' limit={limit}")

        try:
            client = await self._get_client()
            headers = self._build_headers(access_token)

            response = await client.post(
                f"{self.api_url}/api/v1/graphrag/search",
                headers=headers,
                json={
                    "query": query,
                    "limit": limit,
                },
            )
            response.raise_for_status()
            result = response.json()

            # Log result summary
            result_count = len(result) if isinstance(result, list) else result.get("count", "unknown")
            logger.info(f"Document search completed: {result_count} results")

            return result

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Minion API error: status={e.response.status_code}, "
                f"detail={e.response.text[:200]}"
            )
            raise
        except httpx.RequestError as e:
            logger.error(f"Minion connection error: {e}")
            raise

    async def close(self) -> None:
        """
        Close the underlying HTTP client and release resources.

        Call this method when you're done using the client to properly
        clean up connections.
        """
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
            logger.debug("MinionClient closed")


# Singleton instance for efficient connection reuse
_minion_client: Optional[MinionClient] = None


def get_minion_client() -> MinionClient:
    """
    Get the singleton MinionClient instance.

    This function returns a shared client instance with connection pooling
    for optimal performance. The client is lazily initialized on first call.

    Returns:
        Configured MinionClient instance

    Example:
        client = get_minion_client()
        results = await client.search_document("quarterly report")
    """
    global _minion_client
    if _minion_client is None:
        _minion_client = MinionClient()
    return _minion_client
