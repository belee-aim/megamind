from langgraph.graph import StateGraph, END
from langgraph.types import Send
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from typing import List, Optional

from megamind.clients.mcp_client_manager import client_manager
from megamind.configuration import Configuration
from megamind.graph.states import AgentState

# Import nodes
from megamind.graph.nodes.orchestrator import orchestrator_node
from megamind.graph.nodes.planner import planner_node
from megamind.graph.nodes.synthesizer import synthesizer_node
from megamind.graph.nodes.knowledge_capture_node import knowledge_capture_node

# Import subagents
from megamind.graph.agents.business_process_analyst import business_process_analyst
from megamind.graph.agents.workflow_analyst import workflow_analyst
from megamind.graph.agents.report_analyst import report_analyst
from megamind.graph.agents.system_specialist import system_specialist
from megamind.graph.agents.transaction_specialist import transaction_specialist


SPECIALIST_MAP = {
    "business_process": "business_process_analyst",
    "workflow": "workflow_analyst",
    "report": "report_analyst",
    "system": "system_specialist",
    "transaction": "transaction_specialist",
}


def route_after_orchestrator(state: AgentState) -> str | List[Send]:
    """
    Routes from Orchestrator based on its decision.
    Supports parallel execution via Send().
    """
    next_action = state.get("next_action")

    if next_action == "plan":
        return "planner_node"
    elif next_action == "parallel":
        # Send to multiple specialists in parallel
        pending = state.get("pending_specialists", [])
        if pending:
            return [
                Send(SPECIALIST_MAP[s], state) for s in pending if s in SPECIALIST_MAP
            ]
        return END
    elif next_action == "route":
        target = state.get("target_specialist")
        return SPECIALIST_MAP.get(target, END)
    else:  # "respond" or unknown
        return END


def route_after_planner(state: AgentState) -> str | List[Send]:
    """
    Routes from Planner to specialists.
    Supports parallel execution for first group.
    """
    next_action = state.get("next_action")

    if next_action == "parallel":
        pending = state.get("pending_specialists", [])
        if pending:
            return [
                Send(SPECIALIST_MAP[s], state) for s in pending if s in SPECIALIST_MAP
            ]
        return END
    elif next_action == "route":
        target = state.get("target_specialist")
        return SPECIALIST_MAP.get(target, END)
    else:
        return END


def route_after_synthesizer(state: AgentState) -> str | List[Send]:
    """
    Routes from Synthesizer.
    - If more groups, route to next group (potentially parallel)
    - Otherwise, end
    """
    next_action = state.get("next_action")

    if next_action == "parallel":
        pending = state.get("pending_specialists", [])
        if pending:
            return [
                Send(SPECIALIST_MAP[s], state) for s in pending if s in SPECIALIST_MAP
            ]
        return END
    elif next_action == "route":
        target = state.get("target_specialist")
        return SPECIALIST_MAP.get(target, END)
    else:
        return END


async def build_megamind_graph(checkpointer: Optional[AsyncPostgresSaver] = None):
    """
    Builds the LangGraph for the Multi-Agent system.

    Architecture:
    - Orchestrator analyzes and decides: plan, route, parallel, or respond
    - Planner creates multi-step execution plans with parallel grouping
    - Subagents execute specific tasks (can run in parallel)
    - Synthesizer combines results and advances to next group
    """
    client_manager.initialize_client()
    workflow = StateGraph(AgentState, config_schema=Configuration)

    # Add core nodes
    workflow.add_node("orchestrator_node", orchestrator_node)
    workflow.add_node("planner_node", planner_node)
    workflow.add_node("synthesizer_node", synthesizer_node)

    # Add subagent nodes
    workflow.add_node("business_process_analyst", business_process_analyst)
    workflow.add_node("workflow_analyst", workflow_analyst)
    workflow.add_node("report_analyst", report_analyst)
    workflow.add_node("system_specialist", system_specialist)
    workflow.add_node("transaction_specialist", transaction_specialist)

    # Optional: Knowledge capture
    workflow.add_node("knowledge_capture_node", knowledge_capture_node)

    # Set entry point
    workflow.set_entry_point("orchestrator_node")

    # Orchestrator routing (supports parallel via Send)
    workflow.add_conditional_edges(
        "orchestrator_node",
        route_after_orchestrator,
    )

    # Planner routing (supports parallel via Send)
    workflow.add_conditional_edges(
        "planner_node",
        route_after_planner,
    )

    # All subagents go to synthesizer
    workflow.add_edge("business_process_analyst", "synthesizer_node")
    workflow.add_edge("workflow_analyst", "synthesizer_node")
    workflow.add_edge("report_analyst", "synthesizer_node")
    workflow.add_edge("system_specialist", "synthesizer_node")
    workflow.add_edge("transaction_specialist", "synthesizer_node")

    # Synthesizer routing (supports parallel for next group)
    workflow.add_conditional_edges(
        "synthesizer_node",
        route_after_synthesizer,
    )

    # Compile the graph
    app = workflow.compile(checkpointer=checkpointer)
    return app
