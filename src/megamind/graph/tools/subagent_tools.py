"""
Subagent tools for the Orchestrator.
These are wrapper tools that allow the Orchestrator to call subagents.
"""

from langchain_core.tools import tool
from loguru import logger

from megamind.clients.mcp_client_manager import client_manager
from megamind.configuration import Configuration


def inject_token(tool_obj, token):
    """Wrap a tool to inject user_token into kwargs."""
    if not token:
        return tool_obj

    async def wrapped_coroutine(*args, **kwargs):
        kwargs["user_token"] = token
        return await tool_obj.coroutine(*args, **kwargs)

    def wrapped_func(*args, **kwargs):
        kwargs["user_token"] = token
        return tool_obj.func(*args, **kwargs)

    new_tool = tool_obj.copy()
    if tool_obj.coroutine:
        new_tool.coroutine = wrapped_coroutine
    if tool_obj.func:
        new_tool.func = wrapped_func

    return new_tool


@tool
async def create_plan(query: str) -> str:
    """
    Create a plan for complex multi-step tasks.

    Use this tool when the user's request requires multiple steps or
    coordination between different specialists.

    Args:
        query: The user's request that needs to be broken down into steps.

    Returns:
        A structured plan with steps and assigned specialists.
    """
    from langchain_core.messages import SystemMessage, HumanMessage
    from megamind.configuration import Configuration

    logger.debug("---PLANNER TOOL---")

    planner_prompt = """You are the Planner. Create a step-by-step plan for the given query.

## Available Specialists
| Specialist | Use For |
|------------|---------|
| knowledge | Understanding processes, schemas, workflows, organizational info |
| report | Generating and analyzing reports, financial statements |
| operations | CRUD operations, document search, workflow actions (submit, approve) |

## Output Format
Return a JSON array of steps:
```json
[
    {"step": 1, "specialist": "knowledge", "task": "Find the required fields for Sales Order"},
    {"step": 2, "specialist": "operations", "task": "Create the Sales Order with the required fields"}
]
```

Only output the JSON, no additional text."""

    config = Configuration()
    llm = config.get_chat_model()

    messages = [
        SystemMessage(content=planner_prompt),
        HumanMessage(content=query),
    ]

    response = await llm.ainvoke(messages)
    return response.content


@tool
async def call_semantic_analyst(query: str) -> str:
    """
    Call the Semantic Analyst specialist.

    Use this for:
    - Understanding business processes and workflows
    - Getting doctype schemas and field information
    - Searching knowledge graphs for process and workflow definitions
    - Workflow state management and transitions

    Args:
        query: The specific question or task for the Semantic Analyst.

    Returns:
        The specialist's response.
    """
    from langchain.agents import create_agent
    from megamind.graph.tools.zep_graph_tools import (
        search_business_workflows,
        search_employees,
    )
    from megamind.prompts.subagent_prompts import SEMANTIC_ANALYST_PROMPT

    logger.debug("---SEMANTIC ANALYST TOOL---")

    config = Configuration()
    mcp_client = client_manager.get_client()
    llm = config.get_chat_model()

    all_mcp_tools = await mcp_client.get_tools()
    target_tool_names = [
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
        # Workflow tools
        "get_workflow_state",
        "apply_workflow",
    ]
    filtered_mcp_tools = [t for t in all_mcp_tools if t.name in target_tool_names]

    local_tools = [
        search_business_workflows,
        search_employees,
    ]
    tools = filtered_mcp_tools + local_tools

    agent = create_agent(llm, tools=tools, system_prompt=SEMANTIC_ANALYST_PROMPT)
    response = await agent.ainvoke({"messages": [{"role": "user", "content": query}]})

    return response["messages"][-1].content


@tool
async def call_report_analyst(query: str) -> str:
    """
    Call the Report Analyst specialist.

    Use this for:
    - Running query reports
    - Getting financial statements
    - Exporting report data

    Args:
        query: The specific question or task for the Report Analyst.

    Returns:
        The specialist's response.
    """
    from langchain.agents import create_agent
    from megamind.prompts.subagent_prompts import REPORT_ANALYST_PROMPT

    logger.debug("---REPORT ANALYST TOOL---")

    config = Configuration()
    mcp_client = client_manager.get_client()
    llm = config.get_chat_model()

    all_mcp_tools = await mcp_client.get_tools()
    target_tool_names = [
        "run_query_report",
        "get_report_meta",
        "get_report_script",
        "list_reports",
        "export_report",
        "get_financial_statements",
        "run_doctype_report",
    ]
    filtered_mcp_tools = [t for t in all_mcp_tools if t.name in target_tool_names]

    agent = create_agent(
        llm, tools=filtered_mcp_tools, system_prompt=REPORT_ANALYST_PROMPT
    )
    response = await agent.ainvoke({"messages": [{"role": "user", "content": query}]})

    return response["messages"][-1].content


@tool
async def call_system_specialist(query: str) -> str:
    """
    Call the System Specialist.

    Use this for:
    - Creating, reading, updating, deleting documents (CRUD)
    - Searching for documents
    - Checking system health
    - Getting required fields for a doctype

    Args:
        query: The specific question or task for the System Specialist.

    Returns:
        The specialist's response.
    """
    from langchain.agents import create_agent
    from megamind.graph.tools.minion_tools import search_document
    from megamind.graph.tools.titan_knowledge_tools import search_erpnext_knowledge
    from megamind.prompts.subagent_prompts import SYSTEM_SPECIALIST_PROMPT

    logger.debug("---SYSTEM SPECIALIST TOOL---")

    config = Configuration()
    mcp_client = client_manager.get_client()
    llm = config.get_chat_model()

    all_mcp_tools = await mcp_client.get_tools()
    target_tool_names = [
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
        "version",
        "ping",
        "call_method",
        "get_api_instructions",
    ]
    filtered_mcp_tools = [t for t in all_mcp_tools if t.name in target_tool_names]

    local_tools = [search_document, search_erpnext_knowledge]
    tools = filtered_mcp_tools + local_tools

    agent = create_agent(llm, tools=tools, system_prompt=SYSTEM_SPECIALIST_PROMPT)
    response = await agent.ainvoke({"messages": [{"role": "user", "content": query}]})

    return response["messages"][-1].content


# Export all tools for the Orchestrator
ORCHESTRATOR_TOOLS = [
    create_plan,
    call_semantic_analyst,
    call_report_analyst,
    call_system_specialist,
]
