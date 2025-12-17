"""MCP Token Injection Middleware.

This middleware uses LangChain's wrap_tool_call pattern to inject user authentication
tokens into MCP tool calls from the FastAPI request context.
"""

from typing import Awaitable, Callable, Set

from langchain.agents.middleware import AgentMiddleware
from langchain.messages import ToolMessage
from langchain.tools.tool_node import ToolCallRequest
from langgraph.types import Command
from langgraph.errors import GraphInterrupt
from loguru import logger

from megamind.utils.request_context import get_access_token


class MCPTokenMiddleware(AgentMiddleware):
    """Middleware that injects user token from FastAPI request context into MCP tool calls.

    This middleware intercepts all tool calls and adds the user_token argument
    to MCP tools, enabling authenticated access to the ERPNext backend.

    Usage:
        agent = create_agent(
            llm,
            tools=mcp_tools,
            middleware=[MCPTokenMiddleware(mcp_tool_names={"create_document", "get_document"})],
        )
    """

    def __init__(self, mcp_tool_names: Set[str] | None = None):
        """Initialize MCPTokenMiddleware.

        Args:
            mcp_tool_names: Set of tool names that should receive the token.
                           If None, all tools will receive the token.
        """
        super().__init__()
        self.mcp_tool_names = mcp_tool_names

    def _inject_token(self, request: ToolCallRequest) -> str:
        """Inject token into request if applicable. Returns the tool name."""
        tool_name = request.tool_call.get("name", "")

        # Only inject token for MCP tools (or all if no filter specified)
        should_inject = self.mcp_tool_names is None or tool_name in self.mcp_tool_names

        if should_inject:
            token = get_access_token()
            if token:
                # Inject user_token into the tool call arguments
                request.tool_call["args"]["user_token"] = token
                logger.debug(f"Injected user_token into tool: {tool_name}")

        return tool_name

    def _handle_error(self, tool_name: str, e: Exception) -> ToolMessage:
        """Handle tool execution error and return ToolMessage."""
        error_type = type(e).__name__
        error_msg = str(e)
        error_content = (
            f"ERROR: Tool '{tool_name}' failed with {error_type}.\n"
            f"Details: {error_msg}\n\n"
            f"Please adjust your parameters and try again."
        )
        logger.warning(f"Tool {tool_name} failed: {error_msg}")
        return ToolMessage(
            content=error_content,
            tool_call_id="",  # Will be set by caller if needed
        )

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        """Wrap sync tool calls to inject user token from request context.

        Args:
            request: The tool call request containing tool_call info and tools.
            handler: The handler function that executes the tool.

        Returns:
            ToolMessage or Command from the tool execution.
        """
        tool_name = self._inject_token(request)

        try:
            return handler(request)
        except GraphInterrupt:
            raise
        except Exception as e:
            result = self._handle_error(tool_name, e)
            result.tool_call_id = request.tool_call.get("id", "")
            return result

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        """Wrap async tool calls to inject user token from request context.

        Args:
            request: The tool call request containing tool_call info and tools.
            handler: The async handler function that executes the tool.

        Returns:
            ToolMessage or Command from the tool execution.
        """
        tool_name = self._inject_token(request)

        try:
            return await handler(request)
        except GraphInterrupt:
            raise
        except Exception as e:
            result = self._handle_error(tool_name, e)
            result.tool_call_id = request.tool_call.get("id", "")
            return result
