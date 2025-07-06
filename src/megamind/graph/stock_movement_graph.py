from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from megamind.clients.manager import client_manager
from megamind.configuration import Configuration

from .states import AgentState
from .nodes.stock_movement_agent import stock_movement_agent_node

def route_tools_from_stock_movement(state: AgentState) -> str:
    """
    Routes to the appropriate tool node based on the stock movement agent's decision.
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

    # Stock movement agent only uses ERPNext MCP tools
    return "erpnext_mcp_tool_stocks"


async def build_stock_movement_graph(checkpointer: AsyncPostgresSaver = None):
    """
    Builds and compiles the LangGraph for the stock movement agent.
    """
    client_manager.initialize_client()
    workflow = StateGraph(AgentState, config_schema=Configuration)
    mcp_client = client_manager.get_client()

    # Add nodes
    workflow.add_node("stock_movement_agent_node", stock_movement_agent_node)
    tools = await mcp_client.get_tools()
    workflow.add_node("erpnext_mcp_tool_stocks", ToolNode(tools))

    # Set the entry point
    workflow.set_entry_point("stock_movement_agent_node")

    workflow.add_conditional_edges(
        "stock_movement_agent_node",
        route_tools_from_stock_movement,
        {
            "erpnext_mcp_tool_stocks": "erpnext_mcp_tool_stocks",
            END: END,
        },
    )

    workflow.add_edge("erpnext_mcp_tool_stocks", "stock_movement_agent_node")

    # Compile the graph
    app = workflow.compile(checkpointer=checkpointer)
    return app
