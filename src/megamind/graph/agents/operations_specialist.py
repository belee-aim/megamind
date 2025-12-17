from langchain_core.runnables import RunnableConfig
from loguru import logger
from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware

from megamind.clients.mcp_client_manager import client_manager
from megamind.configuration import Configuration
from megamind.graph.states import AgentState
from megamind.graph.middleware.mcp_token_middleware import MCPTokenMiddleware
from megamind.graph.middleware.consent_middleware import ConsentMiddleware
from megamind.prompts.subagent_prompts import OPERATIONS_SPECIALIST_PROMPT


# MCP tool names for operations specialist
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


async def operations_specialist(state: AgentState, config: RunnableConfig):
    """
    Operations Specialist subagent.

    Specializes in:
    - Schema and DocType information (MCP)
    - Document CRUD operations (MCP)
    - Validation and workflow actions (MCP)

    Critical operations (create, update, delete, apply_workflow) require user consent.
    """
    logger.debug("---OPERATIONS SPECIALIST---")

    configurable = Configuration.from_runnable_config(config)
    mcp_client = client_manager.get_client()
    llm = configurable.get_chat_model()

    # Get current task from plan
    current_plan = state.get("current_plan")
    plan_step_index = state.get("plan_step_index", 0)
    task_context = ""
    if current_plan and plan_step_index < len(current_plan):
        task_context = f"\n\nCurrent Task: {current_plan[plan_step_index]['task']}"

    # Get MCP tools (middleware handles token injection and consent)
    all_mcp_tools = await mcp_client.get_tools()
    tools = [t for t in all_mcp_tools if t.name in OPERATIONS_MCP_TOOL_NAMES]

    prompt = OPERATIONS_SPECIALIST_PROMPT + task_context
    agent = create_agent(
        llm,
        tools=tools,
        system_prompt=prompt,
        middleware=[
            MCPTokenMiddleware(mcp_tool_names=OPERATIONS_MCP_TOOL_NAMES),
            ConsentMiddleware(),  # Human-in-the-loop for critical operations
            ToolCallLimitMiddleware(run_limit=10),
        ],
    )

    messages = state.get("messages", [])
    num_old_messages = len(messages)
    response = await agent.ainvoke(state)
    new_messages = response["messages"][num_old_messages:]

    # Store result for orchestrator with specialist identification
    specialist_results = state.get("specialist_results", []) or []
    if new_messages:
        specialist_results.append(
            {
                "specialist": "operations",
                "result": new_messages[-1].content,
            }
        )

    return {
        "specialist_results": specialist_results,
    }
