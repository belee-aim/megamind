"""
Megamind Graph Builder.

This module builds the main LangGraph for the Megamind Multi-Agent system.
Now uses Deep Agents for orchestration, replacing the custom orchestrator/planner/synthesizer pattern.
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from typing import Optional

from megamind.clients.mcp_client_manager import client_manager
from megamind.configuration import Configuration
from megamind.graph.states import AgentState
from megamind.graph.workflows.deep_agent_graph import deep_agent_node
from megamind.graph.nodes.knowledge_capture_node import knowledge_capture_node


async def build_megamind_graph(checkpointer: Optional[AsyncPostgresSaver] = None):
    """
    Builds the LangGraph for the Multi-Agent system.

    Architecture (Deep Agents):
    - Entry: deep_agent_node handles all orchestration and delegation
    - Deep Agents framework manages subagent coordination internally
    - Optional: knowledge_capture_node for post-processing
    - Exit: Graph ends after producing final response

    This replaces the previous architecture with:
    - orchestrator_node
    - planner_node
    - individual subagent nodes
    - synthesizer_node
    - complex conditional routing

    Args:
        checkpointer: Optional checkpointer for state persistence

    Returns:
        Compiled StateGraph
    """
    client_manager.initialize_client()
    workflow = StateGraph(AgentState, config_schema=Configuration)

    # Core node - Deep Agent handles orchestration
    workflow.add_node("deep_agent", deep_agent_node)

    # Optional: Knowledge capture for learning from responses
    workflow.add_node("knowledge_capture_node", knowledge_capture_node)

    # Set entry point
    workflow.set_entry_point("deep_agent")

    # Simple linear flow: deep_agent -> knowledge_capture -> END
    workflow.add_edge("deep_agent", "knowledge_capture_node")
    workflow.add_edge("knowledge_capture_node", END)

    # Compile the graph
    app = workflow.compile(checkpointer=checkpointer)
    return app
