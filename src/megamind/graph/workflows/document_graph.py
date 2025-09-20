from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from megamind.clients.mcp_client_manager import client_manager
from megamind.configuration import Configuration
from megamind.graph.nodes.rag import rag_node
from ..states import AgentState
from ..tools.frappe_retriever import frappe_retriever
from ..nodes.embed import embed_node
from ..nodes.content_agent import content_agent_node
from ..nodes.human_in_the_loop import user_consent_node

interrupt_keywords = [
    "create",
    "update",
    "delete",
    "apply_workflow",
]


def route_tools_from_rag(state: AgentState) -> str:
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

    tool_name = last_message.tool_calls[0]["name"]
    if any(keyword in tool_name.lower() for keyword in interrupt_keywords):
        return "user_consent_node"
    elif tool_name == "frappe_retriever":
        return "frappe_retriever_tool"
    else:
        return "mcp_tools"


def after_consent(state: AgentState) -> str:
    """
    Routes to the next node based on the user's consent.
    """
    if state.get("user_consent_response") == "approved":
        return "mcp_tools"
    else:
        return "rag_node"


async def build_rag_graph(checkpointer: AsyncPostgresSaver = None):
    """
    Builds and compiles the LangGraph for the RAG agent.
    """
    client_manager.initialize_client()
    workflow = StateGraph(AgentState, config_schema=Configuration)
    mcp_client = client_manager.get_client()

    # Add nodes
    workflow.add_node("rag_node", rag_node)
    workflow.add_node("frappe_retriever_tool", ToolNode([frappe_retriever]))
    tools = await mcp_client.get_tools()
    workflow.add_node("mcp_tools", ToolNode(tools))
    workflow.add_node("process_and_embed", embed_node)
    workflow.add_node("content_agent", content_agent_node)
    workflow.add_node("user_consent_node", user_consent_node)

    # Set the entry point
    workflow.set_entry_point("rag_node")

    workflow.add_conditional_edges(
        "rag_node",
        route_tools_from_rag,
        {
            "frappe_retriever_tool": "frappe_retriever_tool",
            "mcp_tools": "mcp_tools",
            "user_consent_node": "user_consent_node",
            END: "content_agent",
        },
    )

    # Add edges
    workflow.add_conditional_edges(
        "user_consent_node",
        after_consent,
        {
            "mcp_tools": "mcp_tools",
            "rag_node": "rag_node",
        },
    )

    # Add edges
    workflow.add_edge("frappe_retriever_tool", "process_and_embed")
    workflow.add_edge("process_and_embed", "rag_node")
    workflow.add_edge("mcp_tools", "rag_node")
    workflow.add_edge("content_agent", END)

    # Compile the graph
    app = workflow.compile(checkpointer=checkpointer)
    return app
