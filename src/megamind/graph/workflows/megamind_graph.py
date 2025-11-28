from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from megamind.clients.mcp_client_manager import client_manager
from megamind.configuration import Configuration
from megamind.graph.nodes.human_in_the_loop import user_consent_node
from megamind.graph.nodes.megamind_agent import megamind_agent_node
from megamind.graph.nodes.corrective_rag_node import corrective_rag_node
from megamind.graph.states import AgentState
from megamind.graph.nodes.knowledge_capture_node import knowledge_capture_node
from megamind.graph.tools.titan_knowledge_tools import (
    search_erpnext_knowledge,
    get_erpnext_knowledge_by_id,
)
from megamind.graph.tools.minion_tools import (
    search_processes,
    search_workflows,
    get_process_definition,
    get_workflow_definition,
    query_workflow_next_steps,
    query_workflow_available_actions,
)

interrupt_keywords = [
    "create",
    "update",
    "delete",
    "apply_workflow",
]


def route_tools_from_rag(state: AgentState) -> str:
    """
    Routes to the appropriate tool node based on the agent's decision.
    Knowledge and process query tools bypass consent checks (read-only).
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

    # Knowledge and process query tools are read-only, bypass consent
    knowledge_tools = [
        "search_erpnext_knowledge",
        "get_erpnext_knowledge_by_id",
        "search_processes",
        "search_workflows",
        "get_process_definition",
        "get_workflow_definition",
        "query_workflow_next_steps",
        "query_workflow_available_actions",
    ]
    if tool_name in knowledge_tools:
        return "mcp_tools"

    # Check if MCP tool requires consent
    if any(keyword in tool_name.lower() for keyword in interrupt_keywords):
        return "user_consent_node"

    return "mcp_tools"


def after_consent(state: AgentState) -> str:
    """
    Routes to the next node based on the user's consent.
    """
    if state.get("user_consent_response") == "approved":
        return "mcp_tools"
    else:
        return "megamind_agent_node"


async def build_megamind_graph(checkpointer: AsyncPostgresSaver = None):
    """
    Builds and compiles the LangGraph for the RAG agent.
    """
    client_manager.initialize_client()
    workflow = StateGraph(AgentState, config_schema=Configuration)
    mcp_client = client_manager.get_client()

    # Add nodes
    workflow.add_node("megamind_agent_node", megamind_agent_node)

    # Combine MCP tools with Titan knowledge search tools and Minion tools
    mcp_tools = await mcp_client.get_tools()
    titan_tools = [search_erpnext_knowledge, get_erpnext_knowledge_by_id]
    minion_tools = [
        search_processes,
        search_workflows,
        get_process_definition,
        get_workflow_definition,
        query_workflow_next_steps,
        query_workflow_available_actions,
    ]
    all_tools = mcp_tools + titan_tools + minion_tools

    workflow.add_node("mcp_tools", ToolNode(all_tools))
    workflow.add_node("corrective_rag_node", corrective_rag_node)
    workflow.add_node("knowledge_capture_node", knowledge_capture_node)
    workflow.add_node("user_consent_node", user_consent_node)

    # Set the entry point
    workflow.set_entry_point("megamind_agent_node")

    workflow.add_conditional_edges(
        "megamind_agent_node",
        route_tools_from_rag,
        {
            "mcp_tools": "mcp_tools",
            "user_consent_node": "user_consent_node",
            END: "knowledge_capture_node",
        },
    )

    # Add edges
    workflow.add_conditional_edges(
        "user_consent_node",
        after_consent,
        {
            "mcp_tools": "mcp_tools",
            "megamind_agent_node": "megamind_agent_node",
        },
    )

    # CRAG: Route tool results through corrective analysis before returning to agent
    # Temporarily disabled CRAG
    # workflow.add_edge("mcp_tools", "corrective_rag_node")
    # workflow.add_edge("corrective_rag_node", "megamind_agent_node")
    # workflow.add_edge("knowledge_capture_node", END)

    workflow.add_edge("mcp_tools", "megamind_agent_node")
    workflow.add_edge("knowledge_capture_node", END)

    # Compile the graph
    app = workflow.compile(checkpointer=checkpointer)
    return app
