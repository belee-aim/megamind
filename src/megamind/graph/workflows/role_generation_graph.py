from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from megamind.clients.manager import client_manager
from megamind.configuration import Configuration
from megamind.graph.nodes.role_generation_agent import (
    generate_role_node,
    reflect_node,
    describe_permissions_node,
)
from megamind.graph.states import RoleGenerationState


def should_continue(state: RoleGenerationState) -> str:
    """
    Determines whether to continue with the reflection loop or end the workflow.
    """
    if state.get("feedback") == "OK":
        return "describe_permissions_node"
    else:
        return "generate_role_node"


async def build_role_generation_graph():
    """
    Builds the role generation workflow with a reflection loop.
    """
    client_manager.initialize_client()
    workflow = StateGraph(RoleGenerationState)
    mcp_client = client_manager.get_client()

    # Add nodes
    workflow.add_node("generate_role_node", generate_role_node)
    tools = await mcp_client.get_tools()
    workflow.add_node("mcp_tools", ToolNode(tools))
    workflow.add_node("reflect_node", reflect_node)
    workflow.add_node("describe_permissions_node", describe_permissions_node)

    # Set the entry point
    workflow.set_entry_point("generate_role_node")

    # Add edges
    workflow.add_conditional_edges(
        "generate_role_node",
        lambda state: (
            "mcp_tools" if state.get("messages")[-1].tool_calls else "reflect_node"
        ),
    )
    workflow.add_edge("mcp_tools", "generate_role_node")
    workflow.add_conditional_edges(
        "reflect_node",
        should_continue,
        {
            "generate_role_node": "generate_role_node",
            "describe_permissions_node": "describe_permissions_node",
        },
    )
    workflow.add_edge("describe_permissions_node", END)

    # Compile the graph
    app = workflow.compile()
    return app
