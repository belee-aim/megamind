import os
from typing import Optional
from loguru import logger
from langchain_mcp_adapters.client import MultiServerMCPClient
from megamind.utils.config import settings


# TODO: Frappe client initialization should receive a cookie or token for authentication
class McpClientManager:
    def __init__(self):
        self._client: Optional[MultiServerMCPClient] = None
        self._is_initialized: bool = False

    def initialize_client(self):
        """Initializes the MCP client if not already initialized."""
        if self._is_initialized:
            logger.debug("MCP client already initialized, skipping...")
            return

        if self._client is None:
            servers_config = {}
            # Add erpnext server if path is configured
            if settings.frappe_mcp_server_path != "none" and os.path.exists(
                settings.frappe_mcp_server_path
            ):
                servers_config["erpnext"] = {
                    "command": "node",
                    "args": [settings.frappe_mcp_server_path],
                    "transport": "stdio",
                    "env": {
                        "FRAPPE_URL": settings.frappe_url,
                        "FRAPPE_API_KEY": settings.frappe_api_key,
                        "FRAPPE_API_SECRET": settings.frappe_api_secret,
                        "AUTH_MODE": settings.frappe_auth_mode,
                        # Add unique identifiers to prevent connection conflicts
                        "SERVER_ID": "erpnext",
                        "PROCESS_ID": str(os.getpid()),
                    },
                }

            # Neo4J MCP server configuration
            if (
                settings.neo4j_uri
                and settings.neo4j_username
                and settings.neo4j_password
            ):
                servers_config["neo4j"] = {
                    "command": "uvx",
                    "args": ["mcp-neo4j-cypher@latest"],
                    "transport": "stdio",
                    "env": {
                        "NEO4J_URI": settings.neo4j_uri,
                        "NEO4J_USERNAME": settings.neo4j_username,
                        "NEO4J_PASSWORD": settings.neo4j_password,
                        # Add unique identifiers to prevent connection conflicts
                        "NEO4J_DATABASE": "neo4j",
                        "PROCESS_ID": str(os.getpid()),
                    },
                }

            if not servers_config:
                raise RuntimeError(
                    "No MCP servers configured. Please set up at least one MCP server."
                )

            logger.info(
                f"Initializing MCP client with servers: {list(servers_config.keys())}"
            )
            self._client = MultiServerMCPClient(servers_config)
            self._is_initialized = True

    async def cleanup(self):
        """Cleanup the MCP client connections."""
        if self._client is None:
            return

        try:
            logger.info("Cleaning up MCP client connections...")
            await self._cleanup_main_client()
            await self._cleanup_server_connections()
            logger.info("MCP client cleanup completed")
        except Exception as e:
            logger.error(f"Error during MCP client cleanup: {e}")
        finally:
            self._client = None
            self._is_initialized = False

    async def _cleanup_main_client(self):
        """Cleanup the main client connection."""
        cleanup_methods = ["close", "cleanup", "disconnect"]
        for method_name in cleanup_methods:
            if hasattr(self._client, method_name):
                method = getattr(self._client, method_name)
                await method()
                logger.debug(f"Called {method_name} on main client")
                break

    async def _cleanup_server_connections(self):
        """Cleanup individual server connections."""
        if not hasattr(self._client, "_servers"):
            return

        for server_name, server in self._client._servers.items():
            if hasattr(server, "close"):
                try:
                    await server.close()
                    logger.debug(f"Closed connection to server: {server_name}")
                except Exception as e:
                    logger.warning(
                        f"Error closing connection to server {server_name}: {e}"
                    )

    def get_client(self) -> MultiServerMCPClient:
        """Returns the MCP client instance."""
        if self._client is None or not self._is_initialized:
            raise RuntimeError("Client not initialized. Call initialize_client first.")
        return self._client

    @property
    def is_initialized(self) -> bool:
        """Check if the client is initialized."""
        return self._is_initialized


client_manager = McpClientManager()
