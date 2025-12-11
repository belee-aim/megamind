from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from typing import Optional
from loguru import logger

from megamind.clients.mcp_client_manager import client_manager
from megamind.configuration import Configuration
from megamind.graph.states import AgentState

# Import nodes
from megamind.graph.nodes.orchestrator import orchestrator_node
from megamind.graph.nodes.knowledge_capture_node import knowledge_capture_node
from megamind.graph.nodes.user_context_node import user_context_node

# Import subagents
from megamind.graph.agents.knowledge_analyst import knowledge_analyst
from megamind.graph.agents.report_analyst import report_analyst
from megamind.graph.agents.operations_specialist import operations_specialist


SPECIALIST_MAP = {
    # Primary names
    "knowledge": "knowledge_analyst",
    "report": "report_analyst",
    "operations": "operations_specialist",
    # Legacy names for backward compatibility
    "business_process": "knowledge_analyst",
    "workflow": "knowledge_analyst",
    "semantic": "knowledge_analyst",
    "system": "operations_specialist",
}


def route_after_orchestrator(state: AgentState) -> str:
    """
    Routes from Orchestrator based on its decision.
    Either routes to a specialist or ends.
    """
    next_action = state.get("next_action")
    target = state.get("target_specialist")

    logger.debug(
        f"route_after_orchestrator: next_action={next_action}, target={target}"
    )

    if next_action == "route":
        destination = SPECIALIST_MAP.get(target, END)
        logger.debug(f"Routing to: {destination}")
        return destination
    else:  # "respond" or unknown
        logger.debug(f"Ending graph (next_action={next_action})")
        return END


async def build_megamind_graph(checkpointer: Optional[AsyncPostgresSaver] = None):
    """
    Builds the LangGraph for the Multi-Agent system.

    Architecture:
    - User Context Node fetches user's personal knowledge from Zep
    - Orchestrator decides: respond directly or route to specialist
    - Subagent executes the task
    - Returns to Orchestrator for synthesis and response
    """
    client_manager.initialize_client()
    workflow = StateGraph(AgentState, config_schema=Configuration)

    # Add core nodes
    workflow.add_node("user_context_node", user_context_node)
    workflow.add_node("orchestrator_node", orchestrator_node)

    # Add subagent nodes
    workflow.add_node("knowledge_analyst", knowledge_analyst)
    workflow.add_node("report_analyst", report_analyst)
    workflow.add_node("operations_specialist", operations_specialist)

    # Optional: Knowledge capture
    workflow.add_node("knowledge_capture_node", knowledge_capture_node)

    # Set entry point - user context first, then orchestrator
    workflow.set_entry_point("user_context_node")
    workflow.add_edge("user_context_node", "orchestrator_node")

    # Orchestrator routing
    workflow.add_conditional_edges(
        "orchestrator_node",
        route_after_orchestrator,
    )

    # All subagents return to orchestrator for synthesis
    workflow.add_edge("knowledge_analyst", "orchestrator_node")
    workflow.add_edge("report_analyst", "orchestrator_node")
    workflow.add_edge("operations_specialist", "orchestrator_node")

    # Compile the graph
    app = workflow.compile(checkpointer=checkpointer)
    return app
