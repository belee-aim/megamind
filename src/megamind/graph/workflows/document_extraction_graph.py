from langgraph.graph import StateGraph, END

from megamind.graph.nodes.document_extraction_agent import (
    extract_facts_node,
    infer_values_node,
)
from megamind.graph.states import DocumentExtractionState


async def build_document_extraction_graph():
    """
    Builds the document extraction workflow.

    This workflow has two nodes:
    1. extract_facts_node: Extracts only explicitly stated information from documents
    2. infer_values_node: Infers missing values based on extracted facts

    Returns:
        Compiled LangGraph application
    """
    workflow = StateGraph(DocumentExtractionState)

    # Add nodes
    workflow.add_node("extract_facts_node", extract_facts_node)
    workflow.add_node("infer_values_node", infer_values_node)

    # Set the entry point
    workflow.set_entry_point("extract_facts_node")

    # Add edges (linear workflow)
    workflow.add_edge("extract_facts_node", "infer_values_node")
    workflow.add_edge("infer_values_node", END)

    # Compile the graph
    app = workflow.compile()
    return app
