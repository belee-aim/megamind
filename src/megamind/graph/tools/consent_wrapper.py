"""
Human-in-the-loop tool wrappers for critical operations.

Wraps MCP tools that perform create/update/delete/apply_workflow operations
to require user consent before execution.
"""

from langgraph.types import interrupt
from langchain_core.tools import BaseTool
from loguru import logger


# Keywords that identify critical operations requiring consent
CRITICAL_KEYWORDS = [
    "create",
    "update",
    "delete",
    "apply_workflow",
]


def requires_consent(tool_name: str) -> bool:
    """Check if a tool name indicates a critical operation requiring consent."""
    return any(keyword in tool_name.lower() for keyword in CRITICAL_KEYWORDS)


def wrap_tool_with_consent(tool: BaseTool) -> BaseTool:
    """
    Wrap a tool to require human consent before execution.

    For critical operations (create, update, delete, apply_workflow),
    this wrapper will interrupt execution and wait for user approval.

    Args:
        tool: The tool to wrap

    Returns:
        Wrapped tool that requests consent before execution
    """
    if not requires_consent(tool.name):
        return tool

    original_coroutine = tool.coroutine
    original_func = tool.func

    async def consent_wrapped_coroutine(*args, **kwargs):
        """Wrapped async execution that requests consent first."""
        logger.debug(f"Critical operation detected: {tool.name}")

        # Build the tool call info for the interrupt
        tool_call_info = {
            "name": tool.name,
            "args": kwargs if kwargs else (args[0] if args else {}),
            "description": tool.description,
        }

        # Interrupt and wait for user consent
        response = interrupt(tool_call_info)

        # Process user response
        if isinstance(response, dict):
            response_type = response.get("type")

            if response_type == "accept":
                # User approved, execute the tool
                logger.debug(f"User approved: {tool.name}")
                if original_coroutine:
                    return await original_coroutine(*args, **kwargs)
                elif original_func:
                    return original_func(*args, **kwargs)

            elif response_type == "edit":
                # User approved with edits
                new_args = response.get("args", {})
                logger.debug(f"User approved with edits: {tool.name}")
                if original_coroutine:
                    return await original_coroutine(**new_args)
                elif original_func:
                    return original_func(**new_args)

        # User denied or invalid response
        logger.debug(f"User denied or cancelled: {tool.name}")
        return f"Action cancelled by user for {tool.name}"

    def consent_wrapped_func(*args, **kwargs):
        """Wrapped sync execution - raises error since we need async for interrupt."""
        raise RuntimeError(
            f"Tool {tool.name} requires consent but was called synchronously. "
            "Use async execution for tools requiring human consent."
        )

    # Create a new tool with the wrapped functions
    new_tool = tool.copy()
    new_tool.coroutine = consent_wrapped_coroutine
    if tool.func:
        new_tool.func = consent_wrapped_func

    return new_tool


def wrap_tools_with_consent(tools: list[BaseTool]) -> list[BaseTool]:
    """
    Wrap a list of tools, adding consent wrappers to critical operations.

    Args:
        tools: List of tools to process

    Returns:
        List of tools with critical operations wrapped for consent
    """
    wrapped = []
    for tool in tools:
        if requires_consent(tool.name):
            logger.debug(f"Wrapping tool for consent: {tool.name}")
            wrapped.append(wrap_tool_with_consent(tool))
        else:
            wrapped.append(tool)
    return wrapped
