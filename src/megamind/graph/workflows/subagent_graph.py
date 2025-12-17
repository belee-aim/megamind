"""Megamind graph using SubAgentMiddleware pattern.

This replaces the traditional LangGraph orchestrator-worker pattern with
a middleware-based approach where specialists are invoked via a `task` tool.

The orchestrator has direct access to read-only tools for quick lookups,
plus can delegate to specialists for complex multi-step operations.
"""

from typing import Optional

from langchain.agents import create_agent
from langchain.agents.middleware import TodoListMiddleware, ToolCallLimitMiddleware
from langchain_core.tools import BaseTool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph.state import CompiledStateGraph
from loguru import logger

from megamind.clients.mcp_client_manager import client_manager
from megamind.configuration import Configuration
from megamind.graph.middleware.subagent_middleware import (
    CompiledSubAgent,
    SubAgentMiddleware,
)
from megamind.graph.middleware.mcp_token_middleware import MCPTokenMiddleware
from megamind.graph.middleware.consent_middleware import ConsentMiddleware
from megamind.graph.tools.minion_tools import search_document
from megamind.graph.tools.titan_knowledge_tools import search_erpnext_knowledge
from megamind.graph.tools.zep_graph_tools import (
    search_business_workflows,
    search_employees,
    search_user_knowledge,
)
from megamind.prompts.subagent_prompts import (
    KNOWLEDGE_ANALYST_PROMPT,
    OPERATIONS_SPECIALIST_PROMPT,
    ORCHESTRATOR_PROMPT,
    REPORT_ANALYST_PROMPT,
    TASK_TOOL_DESCRIPTION,
)


# All MCP tool names that need token injection
REPORT_MCP_TOOL_NAMES = {
    "run_query_report",
    "get_report_meta",
    "get_report_script",
    "list_reports",
    "export_report",
    "get_financial_statements",
    "run_doctype_report",
}

OPERATIONS_MCP_TOOL_NAMES = {
    # Schema/DocType tools
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
    # Document CRUD
    "create_document",
    "get_document",
    "update_document",
    "delete_document",
    "list_documents",
    "check_document_exists",
    "get_document_count",
    # Validation
    "validate_document_enhanced",
    "get_document_status",
    # Link field helpers
    "search_link_options",
    "get_paginated_options",
    # Workflow actions
    "get_workflow_state",
    "apply_workflow",
    # System utilities
    "version",
    "ping",
    "call_method",
    "get_api_instructions",
}


def get_orchestrator_tools() -> list[BaseTool]:
    """Get direct tools for the orchestrator (read-only, quick lookups)."""
    return [
        search_business_workflows,
        search_employees,
        search_user_knowledge,
        search_erpnext_knowledge,
        search_document,
    ]


def get_knowledge_tools() -> list[BaseTool]:
    """Get tools for the knowledge specialist."""
    return [
        search_business_workflows,
        search_employees,
        search_user_knowledge,
        search_erpnext_knowledge,
        search_document,
    ]


async def get_report_tools() -> list[BaseTool]:
    """Get MCP tools for the report specialist."""
    mcp_client = client_manager.get_client()
    all_tools = await mcp_client.get_tools()

    # Filter to target tools (no wrapping - middleware handles token injection)
    filtered = [t for t in all_tools if t.name in REPORT_MCP_TOOL_NAMES]

    # Add knowledge search tool for understanding report filters/best practices
    filtered.append(search_erpnext_knowledge)

    return filtered


async def get_operations_tools() -> list[BaseTool]:
    """Get MCP tools for the operations specialist with consent wrapper."""
    mcp_client = client_manager.get_client()
    all_tools = await mcp_client.get_tools()

    # Filter to target tools (no wrapping - middleware handles token injection)
    filtered = [t for t in all_tools if t.name in OPERATIONS_MCP_TOOL_NAMES]

    # Add knowledge search - MANDATORY before operations per BASE_SYSTEM_PROMPT
    filtered.append(search_erpnext_knowledge)

    # Return filtered tools - ConsentMiddleware handles consent in agent middleware
    return filtered


async def build_subagent_graph(
    checkpointer: Optional[AsyncPostgresSaver] = None,
) -> CompiledStateGraph:
    """Build megamind using subagent middleware pattern.

    The orchestrator has:
    1. Direct access to read-only tools for quick lookups
    2. A `task` tool for delegating to specialists for complex operations

    MCP tools get the access token from request context at runtime via
    set_access_token() called before invoking the graph.

    Args:
        checkpointer: Optional checkpointer for state persistence.

    Returns:
        Compiled agent graph ready for invocation.
    """
    logger.info("Building subagent-based megamind graph")

    # Initialize MCP client
    client_manager.initialize_client()

    # Get configuration and model
    config = Configuration()
    llm = config.get_chat_model()

    # Build specialist agents
    knowledge_agent = create_agent(
        llm,
        tools=get_knowledge_tools(),
        system_prompt=KNOWLEDGE_ANALYST_PROMPT,
        middleware=[ToolCallLimitMiddleware(run_limit=10)],
    )

    report_agent = create_agent(
        llm,
        tools=await get_report_tools(),
        system_prompt=REPORT_ANALYST_PROMPT,
        middleware=[
            MCPTokenMiddleware(mcp_tool_names=REPORT_MCP_TOOL_NAMES),
            ToolCallLimitMiddleware(run_limit=10),
        ],
    )

    operations_agent = create_agent(
        llm,
        tools=await get_operations_tools(),
        system_prompt=OPERATIONS_SPECIALIST_PROMPT,
        middleware=[
            MCPTokenMiddleware(mcp_tool_names=OPERATIONS_MCP_TOOL_NAMES),
            ConsentMiddleware(),  # Human-in-the-loop for critical operations
            ToolCallLimitMiddleware(run_limit=15),
        ],
    )

    # Define subagents for complex tasks
    subagents: list[CompiledSubAgent] = [
        {
            "name": "knowledge",
            "description": "Deep research on business processes, workflows, documentation (Through Knowledge Graph and Vector Search). Use for complex multi-step knowledge gathering.",
            "runnable": knowledge_agent,
        },
        {
            "name": "report",
            "description": "Generate and analyze ERPNext reports, financial data, analytics. Use for complex report queries.",
            "runnable": report_agent,
        },
        {
            "name": "operations",
            "description": "Apply Workflow on a ERPNext Doctype or Create/Read/Update/Delete Doctypes on ERPNext. ONLY agent that can modify data.",
            "runnable": operations_agent,
        },
    ]

    # Build orchestrator with:
    # 1. Direct tools for quick lookups
    # 2. SubAgentMiddleware providing task tool for specialist delegation
    # Note: User context is injected at runtime via SystemMessage in the API layer
    orchestrator = create_agent(
        llm,
        tools=get_orchestrator_tools(),  # Direct read-only tools
        system_prompt=ORCHESTRATOR_PROMPT,
        middleware=[
            TodoListMiddleware(),  # Task planning
            SubAgentMiddleware(
                default_model=llm,
                subagents=subagents,
                general_purpose_agent=False,
                task_description=TASK_TOOL_DESCRIPTION,
            ),
            ToolCallLimitMiddleware(run_limit=30),
        ],
        checkpointer=checkpointer,
    )

    logger.info("Subagent graph built successfully with direct tools + specialists")
    return orchestrator
