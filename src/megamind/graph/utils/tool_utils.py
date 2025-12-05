"""
Centralized tool utilities for Megamind agents.
Replaces duplicated inject_token functions across subagents.
"""

from typing import List, Dict, Any
from loguru import logger


def inject_token(tool, token: str):
    """
    Wrap a tool to inject user_token into kwargs.
    Used for MCP tools that require authentication.

    Args:
        tool: A LangChain-compatible tool
        token: The user's access token to inject

    Returns:
        A wrapped tool with token injection
    """
    if not token:
        return tool

    async def wrapped_coroutine(*args, **kwargs):
        kwargs["user_token"] = token
        return await tool.coroutine(*args, **kwargs)

    def wrapped_func(*args, **kwargs):
        kwargs["user_token"] = token
        return tool.func(*args, **kwargs)

    new_tool = tool.copy()
    if tool.coroutine:
        new_tool.coroutine = wrapped_coroutine
    if tool.func:
        new_tool.func = wrapped_func

    return new_tool


# Tool configurations for each specialist
SPECIALIST_TOOL_CONFIGS: Dict[str, Dict[str, Any]] = {
    "knowledge": {
        "mcp_tools": [
            "find_doctypes",
            "get_module_list",
            "get_doctypes_in_module",
            "check_doctype_exists",
            "get_doctype_schema",
            "get_field_options",
            "get_field_permissions",
            "get_naming_info",
            "get_required_fields",
            "get_frappe_usage_info",
            "get_workflow_state",
            "apply_workflow",
        ],
        "local_tools_module": "megamind.graph.tools.titan_knowledge_tools",
        "local_tools": ["search_erpnext_knowledge", "get_erpnext_knowledge_by_id"],
        "minion_tools": [],
    },
    "report": {
        "mcp_tools": [
            "run_query_report",
            "get_report_meta",
            "get_report_script",
            "list_reports",
            "export_report",
            "get_financial_statements",
            "run_doctype_report",
        ],
        "local_tools_module": None,
        "local_tools": [],
        "minion_tools": [],
    },
    "system": {
        "mcp_tools": [
            "create_document",
            "get_document",
            "update_document",
            "delete_document",
            "list_documents",
            "check_document_exists",
            "get_document_count",
            "validate_document_enhanced",
            "get_document_status",
            "search_link_options",
            "get_paginated_options",
            "get_required_fields",
            "get_doctype_schema",
            "version",
            "ping",
            "call_method",
            "get_api_instructions",
        ],
        "local_tools_module": "megamind.graph.tools.titan_knowledge_tools",
        "local_tools": ["search_erpnext_knowledge"],
        "minion_tools": [],
    },
    "transaction": {
        "mcp_tools": [
            "reconcile_bank_transaction_with_vouchers",
            "create_smart_stock_entry",
        ],
        "local_tools_module": None,
        "local_tools": [],
        "minion_tools": [],
    },
    "document": {
        "mcp_tools": [],
        "local_tools_module": None,
        "local_tools": [],
        "minion_tools": ["search_document"],
    },
}


async def get_mcp_tools_for_specialist(
    mcp_client, specialist_name: str, access_token: str = None
) -> List:
    """
    Get filtered and token-injected MCP tools for a specialist.

    Args:
        mcp_client: The MCP client manager
        specialist_name: One of the SPECIALIST_TOOL_CONFIGS keys
        access_token: Optional user token to inject

    Returns:
        List of configured tools for the specialist
    """
    config = SPECIALIST_TOOL_CONFIGS.get(specialist_name)
    if not config:
        logger.warning(f"Unknown specialist: {specialist_name}")
        return []

    all_mcp_tools = await mcp_client.get_tools()
    target_tool_names = config["mcp_tools"]

    filtered_tools = []
    for tool in all_mcp_tools:
        if tool.name in target_tool_names:
            if access_token:
                tool = inject_token(tool, access_token)
            filtered_tools.append(tool)

    return filtered_tools


def get_local_tools_for_specialist(specialist_name: str) -> List:
    """
    Get local (non-MCP) tools for a specialist.

    Args:
        specialist_name: One of the SPECIALIST_TOOL_CONFIGS keys

    Returns:
        List of local tools
    """
    config = SPECIALIST_TOOL_CONFIGS.get(specialist_name)
    if not config:
        return []

    tools = []

    # Import local tools
    if config.get("local_tools"):
        try:
            from megamind.graph.tools.titan_knowledge_tools import (
                search_erpnext_knowledge,
                get_erpnext_knowledge_by_id,
            )

            tool_map = {
                "search_erpnext_knowledge": search_erpnext_knowledge,
                "get_erpnext_knowledge_by_id": get_erpnext_knowledge_by_id,
            }
            for tool_name in config["local_tools"]:
                if tool_name in tool_map:
                    tools.append(tool_map[tool_name])
        except ImportError as e:
            logger.warning(f"Failed to import local tools: {e}")

    # Import minion tools (only search_document now)
    if config.get("minion_tools"):
        try:
            from megamind.graph.tools.minion_tools import search_document

            tool_map = {
                "search_document": search_document,
            }
            for tool_name in config["minion_tools"]:
                if tool_name in tool_map:
                    tools.append(tool_map[tool_name])
        except ImportError as e:
            logger.warning(f"Failed to import minion tools: {e}")

    return tools
