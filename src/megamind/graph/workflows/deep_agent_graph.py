"""
Deep Agent Graph Builder using LangChain Deep Agents.

This module replaces the custom orchestrator-worker pattern with Deep Agents,
providing built-in task decomposition, context isolation, and subagent coordination.
"""

from typing import Optional, List, Dict, Any
from loguru import logger
from deepagents import create_deep_agent
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langchain_core.runnables import RunnableConfig

from megamind.clients.mcp_client_manager import client_manager
from megamind.configuration import Configuration
from megamind.graph.states import AgentState
from megamind.graph.utils.tool_utils import (
    inject_token,
    get_mcp_tools_for_specialist,
    get_local_tools_for_specialist,
    SPECIALIST_TOOL_CONFIGS,
)
from megamind.prompts.deep_agent_prompts import (
    build_orchestrator_prompt,
    KNOWLEDGE_ANALYST_PROMPT,
    REPORT_ANALYST_PROMPT,
    SYSTEM_SPECIALIST_PROMPT,
    TRANSACTION_SPECIALIST_PROMPT,
    DOCUMENT_SPECIALIST_PROMPT,
)


SPECIALIST_PROMPTS = {
    "knowledge": KNOWLEDGE_ANALYST_PROMPT,
    "report": REPORT_ANALYST_PROMPT,
    "system": SYSTEM_SPECIALIST_PROMPT,
    "transaction": TRANSACTION_SPECIALIST_PROMPT,
    "document": DOCUMENT_SPECIALIST_PROMPT,
}

SPECIALIST_DISPLAY_NAMES = {
    "knowledge": "knowledge-analyst",
    "report": "report-analyst",
    "system": "system-specialist",
    "transaction": "transaction-specialist",
    "document": "document-specialist",
}

SPECIALIST_DESCRIPTIONS = {
    "knowledge": "Understanding business processes, workflows, doctypes, and schemas. Use for questions about how things work, field definitions, process flows, and workflow states.",
    "report": "Generating and analyzing reports. Use for running query reports, financial statements, and data exports.",
    "system": "CRUD operations, document management, widgets, and system health. Use for creating, reading, updating, deleting documents, and API interactions.",
    "transaction": "Handling complex transactions like bank reconciliation and stock entries. Use for financial reconciliation and inventory operations. Requires extra validation.",
    "document": "Graph-based document search. Use for finding documents, records, and entities using natural language queries.",
}


async def build_subagent_configs(
    mcp_client, access_token: str = None
) -> List[Dict[str, Any]]:
    """
    Build subagent configurations for Deep Agents.

    Args:
        mcp_client: The MCP client for tool access
        access_token: User's access token for tool authentication

    Returns:
        List of subagent configuration dicts
    """
    subagents = []

    for specialist_key in SPECIALIST_TOOL_CONFIGS.keys():
        # Get MCP tools with token injection
        mcp_tools = await get_mcp_tools_for_specialist(
            mcp_client, specialist_key, access_token
        )

        # Get local tools
        local_tools = get_local_tools_for_specialist(specialist_key)

        # Combine all tools
        all_tools = mcp_tools + local_tools

        subagent_config = {
            "name": SPECIALIST_DISPLAY_NAMES[specialist_key],
            "description": SPECIALIST_DESCRIPTIONS[specialist_key],
            "system_prompt": SPECIALIST_PROMPTS[specialist_key],
            "tools": all_tools,
        }

        subagents.append(subagent_config)
        logger.debug(
            f"Configured subagent '{specialist_key}' with {len(all_tools)} tools"
        )

    return subagents


async def create_megamind_deep_agent(
    access_token: str = None,
    model: str = None,
    company: str = None,
    current_datetime: str = None,
    user_name: str = None,
    user_email: str = None,
    user_roles: list = None,
    user_department: str = None,
):
    """
    Create the Megamind Deep Agent with all subagents configured.

    Args:
        access_token: User's access token for tool authentication
        model: Optional model override (default from configuration)
        company: Company name for context
        current_datetime: Current datetime string
        user_name: User's full name
        user_email: User's email
        user_roles: User's roles
        user_department: User's department

    Returns:
        Compiled Deep Agent graph
    """
    mcp_client = client_manager.get_client()

    # Build subagent configurations
    subagents = await build_subagent_configs(mcp_client, access_token)

    # Get shared MCP tools for orchestrator (commonly used across specialists)
    all_mcp_tools = await mcp_client.get_tools()
    shared_tool_names = [
        "get_document",
        "list_documents",
        "get_doctype_schema",
        "search_link_options",
    ]

    shared_tools = []
    for tool in all_mcp_tools:
        if tool.name in shared_tool_names:
            if access_token:
                tool = inject_token(tool, access_token)
            shared_tools.append(tool)

    # Build orchestrator prompt with user context
    orchestrator_prompt = build_orchestrator_prompt(
        company=company or "",
        current_datetime=current_datetime or "",
        user_name=user_name or "",
        user_email=user_email or "",
        user_roles=user_roles or [],
        user_department=user_department or "",
    )

    # Get model for Deep Agent (string for supported providers, instance for others)
    config = Configuration()
    model_or_string = model or config.get_model_for_deep_agent()

    # Create the Deep Agent
    agent = create_deep_agent(
        model=model_or_string,
        tools=shared_tools,
        subagents=subagents,
        system_prompt=orchestrator_prompt,
    )

    logger.info(
        f"Created Deep Agent for {company} with model={model_or_string}, {len(subagents)} subagents and {len(shared_tools)} shared tools"
    )

    return agent


async def deep_agent_node(state: AgentState, config: RunnableConfig):
    """
    LangGraph node that wraps the Deep Agent.
    Handles state transformation for graph compatibility.

    Expects user context to be passed via config.configurable:
    - company
    - current_datetime
    - user_name
    - user_email
    - user_roles
    - user_department
    """
    logger.debug("---DEEP AGENT---")

    # Get access token from state
    access_token = state.get("access_token")

    # Get user context from configurable (passed from _handle_chat_stream)
    raw_config = config.get("configurable", {})
    company = raw_config.get("company")
    current_datetime = raw_config.get("current_datetime")
    user_name = raw_config.get("user_name")
    user_email = raw_config.get("user_email")
    user_roles = raw_config.get("user_roles", [])
    user_department = raw_config.get("user_department")

    # Create the deep agent with current user's context
    # Model is determined by settings, not configuration
    agent = await create_megamind_deep_agent(
        access_token=access_token,
        model=None,  # Will use default from settings
        company=company,
        current_datetime=current_datetime,
        user_name=user_name,
        user_email=user_email,
        user_roles=user_roles,
        user_department=user_department,
    )

    # Prepare messages for the agent (exclude old SystemMessage from single-agent pattern)
    messages = state.get("messages", [])

    # Filter out any SystemMessage from old pattern - Deep Agent has its own prompt
    from langchain_core.messages import SystemMessage

    filtered_messages = [m for m in messages if not isinstance(m, SystemMessage)]

    # Invoke the agent
    result = await agent.ainvoke({"messages": filtered_messages})

    # Extract new messages from agent response
    new_messages = result.get("messages", [])

    return {
        "messages": new_messages,
    }


async def build_deep_agent_graph(checkpointer: Optional[AsyncPostgresSaver] = None):
    """
    Build the LangGraph for the Deep Agent Multi-Agent system.

    This is a simplified graph that uses Deep Agents for orchestration,
    replacing the custom orchestrator/planner/synthesizer pattern.

    Architecture:
    - Entry: deep_agent_node handles all orchestration, planning, and delegation
    - Subagents are managed internally by Deep Agents framework
    - Exit: Graph ends after deep agent produces final response

    Args:
        checkpointer: Optional checkpointer for state persistence

    Returns:
        Compiled StateGraph
    """
    client_manager.initialize_client()
    workflow = StateGraph(AgentState, config_schema=Configuration)

    # Single node that handles everything
    workflow.add_node("deep_agent", deep_agent_node)

    # Simple linear flow
    workflow.set_entry_point("deep_agent")
    workflow.add_edge("deep_agent", END)

    # Compile the graph
    app = workflow.compile(checkpointer=checkpointer)

    logger.info("Deep Agent graph built successfully")

    return app
