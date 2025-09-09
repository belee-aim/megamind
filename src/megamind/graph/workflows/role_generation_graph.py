from langgraph.graph import StateGraph, END

from megamind.clients.manager import client_manager
from megamind.graph.nodes.role_generation_agent import (
    generate_role_node,
    describe_permissions_node,
    find_related_role_node,
    get_role_permissions_node,
)
from megamind.graph.states import RoleGenerationState


async def build_role_generation_graph():
    """
    Builds the role generation workflow.
    """
    client_manager.initialize_client()
    workflow = StateGraph(RoleGenerationState)

    # Add nodes
    workflow.add_node("find_related_role_node", find_related_role_node)
    workflow.add_node("get_role_permissions_node", get_role_permissions_node)
    workflow.add_node("generate_role_node", generate_role_node)
    workflow.add_node("describe_permissions_node", describe_permissions_node)

    # Set the entry point
    workflow.set_entry_point("find_related_role_node")

    # Add edges
    workflow.add_edge("find_related_role_node", "get_role_permissions_node")
    workflow.add_edge("get_role_permissions_node", "generate_role_node")
    workflow.add_edge("generate_role_node", "describe_permissions_node")
    workflow.add_edge("describe_permissions_node", END)

    # Compile the graph
    app = workflow.compile()
    return app
