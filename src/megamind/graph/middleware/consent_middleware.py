"""Human-in-the-loop Consent Middleware.

This middleware uses LangChain's wrap_tool_call pattern to intercept critical
operations (create, update, delete, apply_workflow) and request user consent
before execution.

Integrates with Firebase to track interrupt state for the frontend.
"""

from typing import Awaitable, Callable, Set

from langchain.agents.middleware import AgentMiddleware
from langchain.messages import ToolMessage
from langchain.tools.tool_node import ToolCallRequest
from langgraph.types import Command, interrupt
from loguru import logger

from megamind.clients.firebase_client import firebase_client
from megamind.utils.request_context import get_thread_id


# Default keywords that identify critical operations requiring consent
DEFAULT_CRITICAL_KEYWORDS = {
    "create",
    "update",
    "delete",
    "apply_workflow",
}


class ConsentMiddleware(AgentMiddleware):
    """Middleware that requires user consent for critical tool operations.

    This middleware intercepts tool calls that match critical keywords
    (create, update, delete, apply_workflow) and uses LangGraph's interrupt()
    to pause execution and wait for user approval.

    Integrates with Firebase to set interrupt_state for the frontend:
    - Sets interrupt_state=True before interrupt() (graph is waiting)
    - Sets interrupt_state=False after user response (graph can continue)

    Usage:
        agent = create_agent(
            llm,
            tools=mcp_tools,
            middleware=[
                ConsentMiddleware(),  # Uses default keywords
                # Or with custom keywords:
                ConsentMiddleware(critical_keywords={"create", "delete"}),
            ],
        )
    """

    def __init__(
        self,
        critical_keywords: Set[str] | None = None,
        tool_names: Set[str] | None = None,
    ):
        """Initialize ConsentMiddleware.

        Args:
            critical_keywords: Set of keywords that identify critical operations.
                              If None, uses DEFAULT_CRITICAL_KEYWORDS.
            tool_names: Optional set of specific tool names that require consent.
                       If provided, only these tools will require consent
                       (in addition to keyword matching).
        """
        super().__init__()
        self.critical_keywords = critical_keywords or DEFAULT_CRITICAL_KEYWORDS
        self.tool_names = tool_names

    def _requires_consent(self, tool_name: str) -> bool:
        """Check if a tool name indicates a critical operation requiring consent."""
        # Check explicit tool names first
        if self.tool_names and tool_name in self.tool_names:
            return True

        # Check if tool name contains any critical keyword
        tool_name_lower = tool_name.lower()
        return any(keyword in tool_name_lower for keyword in self.critical_keywords)

    def _build_interrupt_info(self, request: ToolCallRequest) -> dict:
        """Build the tool call info for the interrupt.

        Note: ToolCallRequest only provides tool_call dict, not the tool objects,
        so we cannot access tool descriptions here.
        """
        tool_call = request.tool_call

        return {
            "name": tool_call.get("name", ""),
            "args": tool_call.get("args", {}),
        }

    def _process_response(
        self, response, request: ToolCallRequest
    ) -> tuple[bool, dict]:
        """Process user response from interrupt.

        Returns:
            Tuple of (should_execute, args_to_use)
        """
        if isinstance(response, dict):
            response_type = response.get("type")

            if response_type == "accept":
                logger.debug(f"User approved: {request.tool_call.get('name')}")
                return True, request.tool_call.get("args", {})

            elif response_type == "edit":
                new_args = response.get("args", {})
                logger.debug(
                    f"User approved with edits: {request.tool_call.get('name')}"
                )
                # Update the tool call args with user's edits
                request.tool_call["args"] = new_args
                return True, new_args

        logger.debug(f"User denied or cancelled: {request.tool_call.get('name')}")
        return False, {}

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        """Wrap sync tool calls to require consent for critical operations.

        Note: Sync execution will raise an error since interrupt() requires async.
        """
        tool_name = request.tool_call.get("name", "")

        if not self._requires_consent(tool_name):
            return handler(request)

        # Sync consent is not supported - interrupt requires async
        raise RuntimeError(
            f"Tool {tool_name} requires consent but was called synchronously. "
            "Use async execution for tools requiring human consent."
        )

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        """Wrap async tool calls to require consent for critical operations.

        For critical operations, this will:
        1. Set Firebase interrupt_state=True (notify frontend we're waiting)
        2. Call interrupt() to pause execution and wait for user response
        3. Set Firebase interrupt_state=False (user has responded)
        4. Execute or cancel based on user response
        """
        tool_name = request.tool_call.get("name", "")

        if not self._requires_consent(tool_name):
            return await handler(request)

        logger.debug(f"Critical operation detected: {tool_name}")

        # Get thread_id from request context for Firebase
        thread_id = get_thread_id()

        # Set Firebase interrupt state to TRUE (graph is now waiting for consent)
        if thread_id:
            await firebase_client.set_interrupt_state(thread_id, True)
            logger.debug(f"Firebase: Set interrupt_state/{thread_id} = True")

        try:
            # Build interrupt info and wait for user consent
            tool_call_info = self._build_interrupt_info(request)
            response = interrupt(tool_call_info)

            # Process user response
            should_execute, _ = self._process_response(response, request)

            if should_execute:
                return await handler(request)

            # User denied - return cancellation message
            return ToolMessage(
                content=f"Action cancelled by user for {tool_name}",
                tool_call_id=request.tool_call.get("id", ""),
            )
        finally:
            # Clear Firebase interrupt state (user has responded)
            if thread_id:
                await firebase_client.set_interrupt_state(thread_id, False)
                logger.debug(f"Firebase: Set interrupt_state/{thread_id} = False")
