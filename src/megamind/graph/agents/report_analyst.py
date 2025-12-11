from langchain_core.runnables import RunnableConfig
from loguru import logger
from langchain.agents import create_agent

from megamind.clients.mcp_client_manager import client_manager
from megamind.configuration import Configuration
from megamind.graph.states import AgentState
from megamind.prompts.subagent_prompts import REPORT_ANALYST_PROMPT


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


async def report_analyst(state: AgentState, config: RunnableConfig):
    """
    Report Analyst subagent.
    Specializes in generating and retrieving reports.
    """
    logger.debug("---REPORT ANALYST---")

    configurable = Configuration.from_runnable_config(config)
    mcp_client = client_manager.get_client()
    llm = configurable.get_chat_model()
    access_token = state.get("access_token")

    # Get current task from plan
    current_plan = state.get("current_plan")
    plan_step_index = state.get("plan_step_index", 0)
    task_context = ""
    if current_plan and plan_step_index < len(current_plan):
        task_context = f"\n\nCurrent Task: {current_plan[plan_step_index]['task']}"

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

    filtered_mcp_tools = []
    for t in all_mcp_tools:
        if t.name in target_tool_names:
            if access_token:
                t = inject_token(t, access_token)
            filtered_mcp_tools.append(t)

    prompt = REPORT_ANALYST_PROMPT + task_context
    agent = create_agent(llm, tools=filtered_mcp_tools, system_prompt=prompt)

    messages = state.get("messages", [])
    num_old_messages = len(messages)
    response = await agent.ainvoke(state)
    new_messages = response["messages"][num_old_messages:]

    specialist_results = state.get("specialist_results", []) or []
    if new_messages:
        specialist_results.append(new_messages[-1].content)

    return {
        "specialist_results": specialist_results,
    }
