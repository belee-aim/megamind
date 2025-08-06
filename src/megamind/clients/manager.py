from typing import Optional
from langchain_mcp_adapters.client import MultiServerMCPClient
from megamind.utils.config import settings


# TODO: Frappe client initialization should receive a cookie or token for authentication
class ClientManager:
    def __init__(self):
        self._client: Optional[MultiServerMCPClient] = None

    def initialize_client(self):
        """Initializes the MCP client."""
        if self._client is None:
            self._client = MultiServerMCPClient(
                {
                    "erpnext": {
                        "command": "node",
                        "args": [
                            settings.frappe_mcp_server_path
                        ],  # Make this path configurable if needed
                        "transport": "stdio",
                        "env": {
                            "FRAPPE_URL": settings.frappe_url,
                            "FRAPPE_API_KEY": settings.frappe_api_key,
                            "FRAPPE_API_SECRET": settings.frappe_api_secret,
                        },
                    }
                }
            )

    def get_client(self) -> MultiServerMCPClient:
        """Returns the MCP client instance."""
        if self._client is None:
            raise RuntimeError("Client not initialized. Call initialize_client first.")
        return self._client


client_manager = ClientManager()
