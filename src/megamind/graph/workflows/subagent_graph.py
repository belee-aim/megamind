"""Megamind graph using SubAgentMiddleware pattern.

This replaces the traditional LangGraph orchestrator-worker pattern with
a middleware-based approach where specialists are invoked via a `task` tool.
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
from megamind.graph.tools.consent_wrapper import wrap_tools_with_consent
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
    REPORT_ANALYST_PROMPT,
)

# Orchestrator system prompt for subagent-based architecture
ORCHESTRATOR_PROMPT = """# Aimee - AI Assistant

You are Aimee, an intelligent orchestrator helping users with their ERP tasks.

## Your Role

Analyze requests and either respond directly or delegate to specialist subagents:

1. **Respond directly** for greetings, clarification questions, or when synthesizing specialist results
2. **Use specialists** for domain-specific queries:
   - `knowledge`: Business processes, workflows, documentation (READ-ONLY)
   - `report`: Generate and analyze reports, financial data
   - `operations`: CRUD operations, workflow actions (modifies data)

## Multi-Step Operations Pattern

For operations (create, update, delete):
1. First use `knowledge` to understand the business process
2. Then use `operations` to execute the action

## Guidelines

- For parallel independent tasks, invoke multiple specialists concurrently
- Synthesize specialist results into clear, helpful responses
- Ask for missing critical information before proceeding
"""


def _inject_token(tool: BaseTool, token: str) -> BaseTool:
    """Wrap a tool to inject user_token into kwargs."""
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


def get_knowledge_tools() -> list[BaseTool]:
    """Get tools for the knowledge specialist."""
    return [
        search_business_workflows,
        search_employees,
        search_user_knowledge,
        search_erpnext_knowledge,
        search_document,
    ]


async def get_report_tools(access_token: str | None) -> list[BaseTool]:
    """Get MCP tools for the report specialist."""
    mcp_client = client_manager.get_client()
    all_tools = await mcp_client.get_tools()

    target_names = [
        "run_query_report",
        "get_report_meta",
        "get_report_script",
        "list_reports",
        "export_report",
        "get_financial_statements",
        "run_doctype_report",
    ]

    filtered = []
    for t in all_tools:
        if t.name in target_names:
            if access_token:
                t = _inject_token(t, access_token)
            filtered.append(t)

    return filtered


async def get_operations_tools(access_token: str | None) -> list[BaseTool]:
    """Get MCP tools for the operations specialist with consent wrapper."""
    mcp_client = client_manager.get_client()
    all_tools = await mcp_client.get_tools()

    target_names = [
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
    ]

    filtered = []
    for t in all_tools:
        if t.name in target_names:
            if access_token:
                t = _inject_token(t, access_token)
            filtered.append(t)

    # Wrap critical tools with consent mechanism
    return wrap_tools_with_consent(filtered)


async def build_subagent_graph(
    checkpointer: Optional[AsyncPostgresSaver] = None,
    access_token: str | None = None,
) -> CompiledStateGraph:
    """Build megamind using subagent middleware pattern.

    This creates a single orchestrator agent that delegates to specialists
    via the `task` tool provided by SubAgentMiddleware.

    Args:
        checkpointer: Optional checkpointer for state persistence.
        access_token: User's access token for MCP tool authentication.

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
        tools=await get_report_tools(access_token),
        system_prompt=REPORT_ANALYST_PROMPT,
        middleware=[ToolCallLimitMiddleware(run_limit=10)],
    )

    operations_agent = create_agent(
        llm,
        tools=await get_operations_tools(access_token),
        system_prompt=OPERATIONS_SPECIALIST_PROMPT,
        middleware=[ToolCallLimitMiddleware(run_limit=10)],
    )

    # Define subagents
    subagents: list[CompiledSubAgent] = [
        {
            "name": "knowledge",
            "description": "Business processes, workflows, documentation. READ-ONLY. Use for understanding how things work.",
            "runnable": knowledge_agent,
        },
        {
            "name": "report",
            "description": "Generate and analyze reports, financial data, analytics.",
            "runnable": report_agent,
        },
        {
            "name": "operations",
            "description": "CRUD operations, workflow actions, document management. ONLY agent that modifies data.",
            "runnable": operations_agent,
        },
    ]

    # Build orchestrator with middleware
    orchestrator = create_agent(
        llm,
        system_prompt=ORCHESTRATOR_PROMPT,
        middleware=[
            TodoListMiddleware(),  # Task planning
            SubAgentMiddleware(
                default_model=llm,
                subagents=subagents,
                general_purpose_agent=False,  # Only use defined specialists
            ),
            ToolCallLimitMiddleware(run_limit=30),  # Global limit
        ],
        checkpointer=checkpointer,
    )

    logger.info("Subagent graph built successfully")
    return orchestrator
