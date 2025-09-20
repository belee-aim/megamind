from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from megamind.clients.mcp_client_manager import client_manager
from megamind.configuration import Configuration

from megamind.graph.states import AgentState
from megamind.graph.nodes.admin_support_agent import admin_support_agent_node
from megamind.graph.nodes.content_agent import content_agent_node


def route_tools_from_admin_support(state: AgentState) -> str:
    """
    Routes to the appropriate tool node based on the admin support agent's decision.
    """
    if (
        "messages" not in state
        or not isinstance(state["messages"], list)
        or len(state["messages"]) == 0
    ):
        return END

    last_message = state["messages"][-1]
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return END

    # Admin support agent only uses ERPNext MCP tools
    return "erpnext_mcp_tool_admin"


async def build_admin_support_graph(checkpointer: AsyncPostgresSaver = None):
    """
    Builds and compiles the LangGraph for the admin support agent.
    """
    client_manager.initialize_client()
    workflow = StateGraph(AgentState, config_schema=Configuration)
    mcp_client = client_manager.get_client()

    # Add nodes
    workflow.add_node("admin_support_agent_node", admin_support_agent_node)
    tools = await mcp_client.get_tools()
    workflow.add_node("erpnext_mcp_tool_admin", ToolNode(tools))
    workflow.add_node("content_agent", content_agent_node)

    # Set the entry point
    workflow.set_entry_point("admin_support_agent_node")

    workflow.add_conditional_edges(
        "admin_support_agent_node",
        route_tools_from_admin_support,
        {
            "erpnext_mcp_tool_admin": "erpnext_mcp_tool_admin",
            END: "content_agent",
        },
    )

    workflow.add_edge("erpnext_mcp_tool_admin", "admin_support_agent_node")
    workflow.add_edge("content_agent", END)

    # Compile the graph
    app = workflow.compile(checkpointer=checkpointer)
    return app
