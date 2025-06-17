from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition

from megamind.configuration import Configuration

from .states import AgentState
from .nodes.generate import generate_node
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
    workflow.add_node("frappe_retriever_tool", ToolNode([frappe_retriever]))
    workflow.add_node("process_and_embed", embedder_node)
    workflow.add_node("generate", generate_node)

    # Set the entry point
    workflow.set_entry_point("check_cache")

    workflow.add_edge("check_cache", "generate")

    workflow.add_conditional_edges(
        "generate",
        tools_condition,
        {
            "tools": "frappe_retriever_tool",
            END: END
        }
    )

    # Add edges
    workflow.add_edge("frappe_retriever_tool", "process_and_embed")
    workflow.add_edge("process_and_embed", "generate")
    workflow.add_edge("generate", END)

    # Compile the graph
    app = workflow.compile()
    return app