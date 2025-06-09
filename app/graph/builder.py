from langgraph.graph import StateGraph, END

from .state import AgentState
from .nodes.generate import generate_node
from .nodes.check_cache import check_cache_node, should_retrieve_from_frappe
from .nodes.frappe_retriever import frappe_retriever_node
from .nodes.embedder import embedder_node

def build_graph():
    """
    Builds and compiles the LangGraph for the agent.
    """
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("check_cache", check_cache_node)
    workflow.add_node("retrieve_from_frappe", frappe_retriever_node)
    workflow.add_node("process_and_embed", embedder_node)
    workflow.add_node("generate", generate_node)

    # Set the entry point
    workflow.set_entry_point("check_cache")

    # Add conditional edges
    workflow.add_conditional_edges(
        "check_cache",
        should_retrieve_from_frappe,
        {
            "retrieve_from_frappe": "retrieve_from_frappe",
            "process_and_embed": "process_and_embed",
        },
    )

    # Add edges
    workflow.add_edge("retrieve_from_frappe", "process_and_embed")
    workflow.add_edge("process_and_embed", "generate")
    workflow.add_edge("generate", END)

    # Compile the graph
    app = workflow.compile()
    return app
