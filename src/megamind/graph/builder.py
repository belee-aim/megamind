from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition
from loguru import logger

from megamind.clients.manager import client_manager
from megamind.configuration import Configuration
from megamind.graph.nodes.rag import rag_node
from megamind.graph.nodes.router import continue_to_agent, router_node

from .states import AgentState
from .nodes.agent import agent_node
from .nodes.check_cache import check_cache_node
from .tools.frappe_retriever import frappe_retriever
from .nodes.embed import embed_node


def route_tools(state: AgentState) -> str:
    """
    Routes to the appropriate tool node based on the agent's decision.
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

    if last_message.tool_calls[0]["name"] == "frappe_retriever":
        return "frappe_retriever_tool"
    else:
        return "erpnext_mcp_tool"


async def build_graph():
    """
    Builds and compiles the LangGraph for the agent.
    """
    client_manager.initialize_client()
    workflow = StateGraph(AgentState, config_schema=Configuration)
    mcp_client = client_manager.get_client()

    # Add nodes
    workflow.add_node("check_cache", check_cache_node)
    workflow.add_node("router_node", router_node)
    workflow.add_node("agent_node", agent_node)
    workflow.add_node("rag_node", rag_node)
    workflow.add_node("frappe_retriever_tool", ToolNode([frappe_retriever]))
    tools = await mcp_client.get_tools()
    workflow.add_node("erpnext_mcp_tool", ToolNode(tools))
    workflow.add_node("process_and_embed", embed_node)

    # Set the entry point
    workflow.set_entry_point("check_cache")

    workflow.add_edge("check_cache", "router_node")
    workflow.add_conditional_edges(
        "router_node", continue_to_agent, ["rag_node", "agent_node"]
    )

    workflow.add_conditional_edges(
        "agent_node",
        route_tools,
        {
            "frappe_retriever_tool": "frappe_retriever_tool",
            "erpnext_mcp_tool": "erpnext_mcp_tool",
            END: END,
        },
    )

    workflow.add_conditional_edges(
        "rag_node",
        tools_condition,
        {
            "frappe_retriever_tool": "frappe_retriever_tool",
            END: END,
        },
    )

    # Add edges
    workflow.add_edge("frappe_retriever_tool", "process_and_embed")
    workflow.add_conditional_edges(
        "process_and_embed", continue_to_agent, ["rag_node", "agent_node"]
    )
    workflow.add_edge("erpnext_mcp_tool", "agent_node")

    # Compile the graph
    app = workflow.compile()
    return app
