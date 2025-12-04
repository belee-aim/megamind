from langchain_core.runnables import RunnableConfig
from loguru import logger
from langchain.agents import create_agent

from megamind.clients.mcp_client_manager import client_manager
from megamind.configuration import Configuration
from megamind.graph.states import AgentState
from megamind.graph.tools.titan_knowledge_tools import (
    search_erpnext_knowledge,
    get_erpnext_knowledge_by_id,
)
from megamind.graph.tools.minion_tools import (
    search_processes,
    get_process_definition,
)
from megamind.prompts.subagent_prompts import BUSINESS_PROCESS_ANALYST_PROMPT


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


async def business_process_analyst(state: AgentState, config: RunnableConfig):
    """
    Business Process Analyst subagent.
    Specializes in understanding business processes, doctypes, and schemas.
    """
    logger.debug("---BUSINESS PROCESS ANALYST---")

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

    # Get MCP tools
    all_mcp_tools = await mcp_client.get_tools()
    target_tool_names = [
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
    ]

    filtered_mcp_tools = []
    for t in all_mcp_tools:
        if t.name in target_tool_names:
            if access_token:
                t = inject_token(t, access_token)
            filtered_mcp_tools.append(t)

    local_tools = [
        search_erpnext_knowledge,
        get_erpnext_knowledge_by_id,
        search_processes,
        get_process_definition,
    ]
    tools = filtered_mcp_tools + local_tools

    # Create agent
    prompt = BUSINESS_PROCESS_ANALYST_PROMPT + task_context
    agent = create_agent(llm, tools=tools, system_prompt=prompt)

    # Invoke agent
    messages = state.get("messages", [])
    num_old_messages = len(messages)
    response = await agent.ainvoke(state)
    new_messages = response["messages"][num_old_messages:]

    # Store result for synthesizer
    specialist_results = state.get("specialist_results", []) or []
    if new_messages:
        specialist_results.append(new_messages[-1].content)

    return {
        "messages": new_messages,
        "specialist_results": specialist_results,
    }
