from langchain_core.runnables import RunnableConfig
from loguru import logger
from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware

from megamind.clients.mcp_client_manager import client_manager
from megamind.configuration import Configuration
from megamind.graph.states import AgentState
from megamind.graph.middleware.mcp_token_middleware import MCPTokenMiddleware
from megamind.prompts.subagent_prompts import REPORT_ANALYST_PROMPT


# MCP tool names for report analyst
REPORT_MCP_TOOL_NAMES = {
    "run_query_report",
    "get_report_meta",
    "get_report_script",
    "list_reports",
    "export_report",
    "get_financial_statements",
    "run_doctype_report",
}


async def report_analyst(state: AgentState, config: RunnableConfig):
    """
    Report Analyst subagent.
    Specializes in generating and retrieving reports.
    """
    logger.debug("---REPORT ANALYST---")

    configurable = Configuration.from_runnable_config(config)
    mcp_client = client_manager.get_client()
    llm = configurable.get_chat_model()

    # Get current task from plan
    current_plan = state.get("current_plan")
    plan_step_index = state.get("plan_step_index", 0)
    task_context = ""
    if current_plan and plan_step_index < len(current_plan):
        task_context = f"\n\nCurrent Task: {current_plan[plan_step_index]['task']}"

    # Get MCP tools (no wrapping - middleware handles token injection)
    all_mcp_tools = await mcp_client.get_tools()
    filtered_mcp_tools = [t for t in all_mcp_tools if t.name in REPORT_MCP_TOOL_NAMES]

    prompt = REPORT_ANALYST_PROMPT + task_context
    agent = create_agent(
        llm,
        tools=filtered_mcp_tools,
        system_prompt=prompt,
        middleware=[
            MCPTokenMiddleware(mcp_tool_names=REPORT_MCP_TOOL_NAMES),
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
                "specialist": "report",
                "result": new_messages[-1].content,
            }
        )

    return {
        "specialist_results": specialist_results,
    }
