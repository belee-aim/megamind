"""Megamind graph using SubAgentMiddleware pattern.

The orchestrator delegates ALL work to specialist subagents via the `task` tool:
- knowledge: The SOLE GATEWAY for all knowledge queries (workflows, employees, docs)
- report: Report generation and financial analytics
- operations: Document CRUD and workflow actions (the only agent that modifies data)

The orchestrator has NO direct tools - it uses the knowledge subagent first,
then delegates to other specialists with context from knowledge.
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
    # "call_method", # Commented because agent keeps using this method for state changing actions.
    "get_api_instructions",
}


# Note: Orchestrator has NO direct tools - uses task tool to delegate to knowledge subagent
# This ensures knowledge subagent is the sole gateway for all knowledge queries


def get_knowledge_tools() -> list[BaseTool]:
    """Get tools for the knowledge specialist.

    The knowledge subagent is the SOLE GATEWAY for all knowledge queries:
    - Business workflows: Company processes, approval chains, SOPs
    - Employees: Org structure, departments, roles, reporting relationships
    - User knowledge: Personal context, preferences, past interactions
    - ERPNext knowledge: DocType schemas, field rules, best practices, documentation
    - Documents: Files in the Document Management System (DMS)

    The orchestrator delegates ALL knowledge lookups to this subagent.
    """
    return [
        search_business_workflows,
        search_employees,
        search_user_knowledge,
        search_erpnext_knowledge,
        search_document,
    ]


async def get_report_tools() -> list[BaseTool]:
    """Get MCP tools for the report specialist.

    Report subagent focuses ONLY on report execution:
    - Query/script reports, financial statements, doctype reports
    - Export functionality

    Knowledge context (report filters, best practices) should be provided
    in the task description by the orchestrator after consulting knowledge subagent.
    """
    mcp_client = client_manager.get_client()
    all_tools = await mcp_client.get_tools()

    # Filter to report tools only - no knowledge tools
    return [t for t in all_tools if t.name in REPORT_MCP_TOOL_NAMES]


async def get_operations_tools() -> list[BaseTool]:
    """Get MCP tools for the operations specialist.

    Operations subagent focuses ONLY on document operations:
    - CRUD: create, read, update, delete documents
    - Workflow: apply workflow actions (submit, approve, reject)
    - Schema: get doctype info, required fields, field options

    Required field validation and best practices should be provided
    in the task description by the orchestrator after consulting knowledge subagent.
    """
    mcp_client = client_manager.get_client()
    all_tools = await mcp_client.get_tools()

    # Filter to operations tools only - no knowledge tools
    return [t for t in all_tools if t.name in OPERATIONS_MCP_TOOL_NAMES]


async def build_subagent_graph(
    checkpointer: Optional[AsyncPostgresSaver] = None,
) -> CompiledStateGraph:
    """Build megamind using subagent middleware pattern.

    Architecture:
    - Orchestrator has NO direct tools
    - Uses `task` tool to delegate to specialist subagents
    - Knowledge subagent is the sole gateway for all knowledge queries
    - Report and Operations subagents focus on their core MCP tools

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
    # NOTE: Knowledge subagent is the SOLE GATEWAY for all knowledge - orchestrator has no direct tools
    subagents: list[CompiledSubAgent] = [
        {
            "name": "knowledge",
            "description": (
                "SOLE GATEWAY for all organizational knowledge. Use this subagent FIRST for:\n"
                "- Business workflows, approval processes, SOPs\n"
                "- Employee info, org structure, departments, roles\n"
                "- User preferences and past context\n"
                "- ERPNext documentation, DocType schemas, field validation rules\n"
                "- Finding documents in DMS\n\n"
                "ALWAYS consult knowledge BEFORE operations (to get required fields) or reports (to get filter requirements)."
            ),
            "runnable": knowledge_agent,
        },
        {
            "name": "report",
            "description": (
                "Generate and analyze system reports, financial statements, and analytics.\n"
                "Has access to: run_query_report, get_report_meta, list_reports, get_financial_statements, export_report.\n\n"
                "NOTE: Does NOT have knowledge search. Provide relevant context (filters, best practices) from knowledge in the task description."
            ),
            "runnable": report_agent,
        },
        {
            "name": "operations",
            "description": (
                "Execute document operations and workflow actions. The ONLY agent that can modify data.\n"
                "Has access to: create/get/update/delete_document, apply_workflow, get_doctype_schema, get_required_fields, list_documents.\n\n"
                "NOTE: Does NOT have knowledge search. Provide required fields and validation rules from knowledge in the task description."
            ),
            "runnable": operations_agent,
        },
    ]

    # Build orchestrator with:
    # - NO direct tools - all knowledge queries go through knowledge subagent
    # - SubAgentMiddleware provides the `task` tool for specialist delegation
    # Note: User context is injected at runtime via SystemMessage in the API layer
    orchestrator = create_agent(
        llm,
        tools=[],  # No direct tools - delegates everything via task tool
        system_prompt=ORCHESTRATOR_PROMPT,
        middleware=[
            TodoListMiddleware(),  # Task planning
            SubAgentMiddleware(
                default_model=llm,
                subagents=subagents,
                general_purpose_agent=False,
                task_description=TASK_TOOL_DESCRIPTION,
                system_prompt=None,  # ORCHESTRATOR_PROMPT already has complete instructions
            ),
            ToolCallLimitMiddleware(run_limit=30),
        ],
        checkpointer=checkpointer,
    )

    logger.info(
        "Subagent graph built: orchestrator delegates via task tool to knowledge/report/operations"
    )
    return orchestrator
