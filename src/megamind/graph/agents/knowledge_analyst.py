from langchain_core.runnables import RunnableConfig
from loguru import logger
from langchain.agents import create_agent

from megamind.configuration import Configuration
from megamind.graph.states import AgentState
from megamind.graph.tools.zep_graph_tools import (
    search_business_workflows,
    search_employees,
)
from megamind.graph.tools.minion_tools import search_document
from megamind.graph.tools.titan_knowledge_tools import search_erpnext_knowledge
from megamind.prompts.subagent_prompts import KNOWLEDGE_ANALYST_PROMPT


async def knowledge_analyst(state: AgentState, config: RunnableConfig):
    """
    Knowledge Analyst subagent.

    Specializes in understanding business processes, workflows, and documentation.
    Uses Zep knowledge graphs plus local search tools for:
    - Business processes and workflows (business_workflows_json graph)
    - Employee/organizational information (employees graph)
    - System documentation and best practices (search_erpnext_knowledge)
    - Document search in DMS (search_document)

    This agent is READ-ONLY - no MCP tools that modify data.
    """
    logger.debug("---KNOWLEDGE ANALYST---")

    configurable = Configuration.from_runnable_config(config)
    llm = configurable.get_chat_model()

    # Get current task from plan if executing a plan
    current_plan = state.get("current_plan")
    plan_step_index = state.get("plan_step_index", 0)
    task_context = ""
    if current_plan and plan_step_index < len(current_plan):
        task_context = f"\n\nCurrent Task: {current_plan[plan_step_index]['task']}"

    # All local/read-only tools - no MCP tools
    tools = [
        # Zep graph search tools
        search_business_workflows,
        search_employees,
        # Local search tools
        search_erpnext_knowledge,
        search_document,
    ]

    # Create agent
    prompt = KNOWLEDGE_ANALYST_PROMPT + task_context
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
        "specialist_results": specialist_results,
    }
