from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from megamind.clients.mcp_client_manager import client_manager
from megamind.configuration import Configuration

from megamind.graph.states import AgentState
from megamind.graph.nodes.bank_reconciliation_agent import (
    bank_reconciliation_agent_node,
)
from megamind.graph.nodes.content_agent import content_agent_node
from megamind.graph.nodes.integrations.bank_reconciliation_model import (
    bank_reconciliation_model_node,
)


def route_tools_from_bank_reconciliation(state: AgentState) -> str:
    """
    Routes to the appropriate tool node based on the bank reconciliation agent's decision.
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

    # Bank reconciliation agent only uses ERPNext MCP tools
    return "erpnext_mcp_tool_bank"


async def build_bank_reconciliation_graph(checkpointer: AsyncPostgresSaver = None):
    """
    Builds and compiles the LangGraph for the bank reconciliation agent.
    """
    client_manager.initialize_client()
    workflow = StateGraph(AgentState, config_schema=Configuration)
    mcp_client = client_manager.get_client()

    # Add nodes
    workflow.add_node("bank_reconciliation_agent_node", bank_reconciliation_agent_node)
    tools = await mcp_client.get_tools()
    workflow.add_node("erpnext_mcp_tool_bank", ToolNode(tools))
    workflow.add_node("content_agent", content_agent_node)
    workflow.add_node("bank_reconciliation_model", bank_reconciliation_model_node)

    # Set the entry point
    workflow.set_entry_point("bank_reconciliation_agent_node")

    workflow.add_conditional_edges(
        "bank_reconciliation_agent_node",
        route_tools_from_bank_reconciliation,
        {
            "erpnext_mcp_tool_bank": "erpnext_mcp_tool_bank",
            END: "bank_reconciliation_model",
        },
    )

    workflow.add_edge("erpnext_mcp_tool_bank", "bank_reconciliation_agent_node")
    workflow.add_edge("bank_reconciliation_model", "content_agent")
    workflow.add_edge("content_agent", END)

    # Compile the graph
    app = workflow.compile(checkpointer=checkpointer)
    return app
