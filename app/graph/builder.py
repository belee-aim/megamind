from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from .state import AgentState
from .nodes import generate_node # retrieve_node will be replaced by ToolNode
from .tools.retriever import get_retriever_tool

def build_graph():
    """
    Builds and compiles the LangGraph for the agent.
    """
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("retrieve", ToolNode([get_retriever_tool()]))
    workflow.add_node("generate", generate_node)
    # Add other nodes here as needed

    # Set the entry point
    workflow.set_entry_point("retrieve")

    # Add edges
    # The ToolNode will return a list of ToolMessages, which will be added to the state.
    # The 'generate' node will then need to process these ToolMessages.
    workflow.add_edge("retrieve", "generate")
    workflow.add_edge("generate", END)
    # Add edges between nodes here as needed

    # Compile the graph
    app = workflow.compile()
    return app
