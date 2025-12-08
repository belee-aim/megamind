from langchain_core.runnables import RunnableConfig
from loguru import logger
from langchain.agents import create_agent

from megamind.clients.mcp_client_manager import client_manager
from megamind.configuration import Configuration
from megamind.graph.states import AgentState
from megamind.graph.tools.zep_graph_tools import (
    search_business_workflows,
    search_employees,
)
from megamind.graph.tools.consent_wrapper import wrap_tools_with_consent
from megamind.prompts.subagent_prompts import SEMANTIC_ANALYST_PROMPT


def inject_token(tool, token):
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


async def semantic_analyst(state: AgentState, config: RunnableConfig):
    """
    Semantic Analyst subagent.

    Specializes in understanding business processes, workflows, doctypes, and schemas.
    Uses Zep knowledge graphs to search for:
    - Business processes and workflows (business_workflows_json graph)
    - Employee/organizational information (employees graph)

    Also uses MCP tools for:
    - DocType schema operations
    - Workflow state management (apply_workflow requires consent)
    """
    logger.debug("---SEMANTIC ANALYST---")

    configurable = Configuration.from_runnable_config(config)
    mcp_client = client_manager.get_client()
    llm = configurable.get_chat_model()
    access_token = state.get("access_token")

    # Get current task from plan if executing a plan
    current_plan = state.get("current_plan")
    plan_step_index = state.get("plan_step_index", 0)
    task_context = ""
    if current_plan and plan_step_index < len(current_plan):
        task_context = f"\n\nCurrent Task: {current_plan[plan_step_index]['task']}"

    # Get MCP tools for schema and workflow operations
    all_mcp_tools = await mcp_client.get_tools()
    target_tool_names = [
        # Schema/DocType tools (READ-ONLY)
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
        # Workflow state (READ-ONLY - checking state, not transitioning)
        "get_workflow_state",
    ]

    filtered_mcp_tools = []
    for t in all_mcp_tools:
        if t.name in target_tool_names:
            if access_token:
                t = inject_token(t, access_token)
            filtered_mcp_tools.append(t)

    # Wrap critical MCP tools with consent (apply_workflow)
    filtered_mcp_tools = wrap_tools_with_consent(filtered_mcp_tools)

    # Zep graph search tools
    local_tools = [
        search_business_workflows,
        search_employees,
    ]
    tools = filtered_mcp_tools + local_tools

    # Create agent
    prompt = SEMANTIC_ANALYST_PROMPT + task_context
    agent = create_agent(llm, tools=tools, system_prompt=prompt)

    # Invoke agent
    messages = state.get("messages", [])
    num_old_messages = len(messages)
    response = await agent.ainvoke(state)
    new_messages = response["messages"][num_old_messages:]

    # Store result for orchestrator
    specialist_results = state.get("specialist_results", []) or []
    if new_messages:
        specialist_results.append(new_messages[-1].content)

    return {
        "messages": new_messages,
        "specialist_results": specialist_results,
    }
