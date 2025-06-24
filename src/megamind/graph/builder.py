from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition

from megamind.configuration import Configuration

from .states import AgentState
from .nodes.agent import agent_node
from .nodes.check_cache import check_cache_node
from .tools.frappe_retriever import frappe_retriever
from .nodes.embedder import embedder_node

def build_graph():
    """
    Builds and compiles the LangGraph for the agent.
    """
    workflow = StateGraph(AgentState, config_schema=Configuration)

    # Add nodes
    workflow.add_node("check_cache", check_cache_node)
    workflow.add_node("agent", agent_node)
    workflow.add_node("frappe_retriever_tool", ToolNode([frappe_retriever]))
    workflow.add_node("process_and_embed", embedder_node)

    # Set the entry point
    workflow.set_entry_point("check_cache")
    workflow.add_edge("check_cache", "agent")

    workflow.add_conditional_edges(
        "agent",
        tools_condition,
        {
            "tools": "frappe_retriever_tool",
            END: END
        }
    )

    # Add edges
    workflow.add_edge("frappe_retriever_tool", "process_and_embed")
    workflow.add_edge("process_and_embed", "agent")

    # Compile the graph
    app = workflow.compile()
    return app
