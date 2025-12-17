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
    REPORT_ANALYST_PROMPT,
)

# Custom task tool description with ERPNext-specific few-shot examples
# NOTE: This is internal knowledge for the AI - never expose "ERPNext" to users
TASK_TOOL_DESCRIPTION = """Launch an ephemeral subagent to handle complex, multi-step independent tasks with isolated context windows.

Available agent types and the tools they have access to:
{available_agents}

When using the Task tool, you must specify a subagent_type parameter to select which agent type to use.

## SYSTEM CONTEXT (INTERNAL - DO NOT EXPOSE TO USER)
You are operating with ERPNext as the underlying ERP system. All doctypes, workflows, schemas, and business logic are ERPNext-native. When communicating with users, refer to it as "the system" or "the platform" - never mention "ERPNext" directly.

## Usage notes:
1. Launch multiple agents concurrently whenever possible, to maximize performance; to do that, use a single message with multiple tool uses
2. When the agent is done, it will return a single message back to you. The result returned by the agent is not visible to the user. To show the user the result, you should send a text message back to the user with a concise summary of the result.
3. Each agent invocation is stateless. You will not be able to send additional messages to the agent, nor will the agent be able to communicate with you outside of its final report. Therefore, your prompt should contain a highly detailed task description for the agent to perform autonomously and you should specify exactly what information the agent should return back to you in its final and only message to you.
4. The agent's outputs should generally be trusted
5. Clearly tell the agent whether you expect it to create content, perform analysis, or just do research (search, file reads, web fetches, etc.), since it is not aware of the user's intent

## ERPNext-Specific Examples:

### Operations Specialist Examples (create/update/delete documents):

<example>
User: "I want to create a sales order"
Assistant: *Uses the task tool with operations specialist*
task(description="Create a Sales Order for the user. First check required fields, then gather customer and item details interactively.", subagent_type="operations")
<commentary>
Document creation is a multi-step process requiring schema lookup, field validation, and interactive gathering of required data. The operations specialist handles this workflow end-to-end.
</commentary>
</example>

<example>
User: "Submit my purchase order PO-2024-001"
Assistant: *Uses the task tool with operations specialist*
task(description="Apply workflow action 'Submit' on Purchase Order PO-2024-001. Validate the document is ready for submission first.", subagent_type="operations")
<commentary>
Workflow state transitions require validation and may have approval requirements. The operations specialist can check prerequisites and apply the workflow action.
</commentary>
</example>

<example>
User: "Delete material request MREQ-2024-050 and also MREQ-2024-051"
Assistant: *Launches two parallel task calls for operations specialist*
task(description="Delete Material Request MREQ-2024-050", subagent_type="operations")
task(description="Delete Material Request MREQ-2024-051", subagent_type="operations")
<commentary>
Each deletion is independent. Launching them in parallel saves time while the operations specialist handles any validations needed before deletion.
</commentary>
</example>

### Report Specialist Examples (analytics and financial data):

<example>
User: "Show me the accounts receivable aging report"
Assistant: *Uses the task tool with report specialist*
task(description="Generate the Accounts Receivable Aging report for the current company. Summarize the aging buckets and highlight overdue amounts.", subagent_type="report")
<commentary>
Report generation requires understanding filter requirements, executing the report, and summarizing results. The report specialist handles this workflow.
</commentary>
</example>

<example>
User: "I need a comparison of Q1 vs Q2 revenue"
Assistant: *Launches two parallel task calls for report specialist*
task(description="Get revenue figures from P&L statement for Q1 2024", subagent_type="report")
task(description="Get revenue figures from P&L statement for Q2 2024", subagent_type="report")
Assistant: *Synthesizes results into comparison table*
<commentary>
Each quarter's data can be fetched independently in parallel. The orchestrator then combines and compares the results.
</commentary>
</example>

### Knowledge Specialist Examples (deep research):

<example>
User: "Explain the complete sales cycle in our company and what approvals are needed"
Assistant: *Uses the task tool with knowledge specialist*
task(description="Research the complete sales cycle workflow from Lead to Payment Entry. Include all approval stages, state transitions, and responsible roles.", subagent_type="knowledge")
<commentary>
Deep business process research requires searching multiple knowledge graphs and synthesizing the workflow. The knowledge specialist can do comprehensive research and return a consolidated answer.
</commentary>
</example>

### Direct Tools (DO NOT use task tool):

<example>
User: "What is a Sales Order?"
Assistant: *Uses search_erpnext_knowledge directly without task tool*
<commentary>
Simple knowledge lookups should use direct tools. The task tool adds overhead for trivial queries.
</commentary>
</example>

<example>
User: "Who manages the Finance department?"
Assistant: *Uses search_employees directly without task tool*
<commentary>
Quick organizational lookups don't need a subagent. Direct tools are faster for simple queries.
</commentary>
</example>

<example>
User: "Show me my pending tasks"
Assistant: *Uses search_erpnext_knowledge directly (might be a widget)*
<commentary>
Widget queries should use direct tools. If is_widget: true is returned, immediately pass through the widget XML.
</commentary>
</example>
"""

# Orchestrator system prompt - focuses on identity, tools overview, and output formats
# Detailed task routing examples are in TASK_TOOL_DESCRIPTION to avoid duplication
ORCHESTRATOR_PROMPT = """# Aimee - AI Assistant

You are Aimee, an intelligent and proactive assistant specialized in helping with business operations.

**CRITICAL: Do not mention ERPNext - refer to it as "the system" or "the platform".**

## Your Tools

### Direct Tools (for quick lookups):
- `search_business_workflows`: Business processes, workflow definitions, approval chains
- `search_employees`: Employee and organizational information
- `search_user_knowledge`: User's personal knowledge graph
- `search_erpnext_knowledge`: Documentation, field rules, best practices
- `search_document`: Documents in DMS

### `task` Tool (for delegating to specialists):
Use the `task` tool to delegate complex multi-step work to specialist subagents.
See the `task` tool description for detailed usage examples and decision logic.

## Proactive Workflow

1. When asked about a process, use direct tools to explain it
2. When asked to PERFORM an action (create, update, delete), delegate via `task`
3. After specialist returns, summarize the result to the user
4. Suggest next steps based on the workflow

## Widget System - HIGHEST PRIORITY

When `search_erpnext_knowledge` returns knowledge with `is_widget: true`:
1. **IMMEDIATELY return the widget XML** from the content field
2. **DO NOT** make any additional tool calls

## Display XML Formats

**For document details:**
```xml
<function>
  <doc_item>
    <doctype>Sales Order</doctype>
    <name>SO-2024-00123</name>
  </doc_item>
</function>
```

**For lists:**
```xml
<function>
  <render_list>
    <title>Recent Orders</title>
    <list>
      <list_item>SO-2024-00123 - Customer A</list_item>
    </list>
  </render_list>
</function>
```
"""


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
