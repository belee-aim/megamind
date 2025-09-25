from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.base import BaseCheckpointSaver

from megamind.graph.nodes.minion_agent import document_agent_node
from megamind.graph.states import AgentState
from megamind.graph.tools.minion_tools import search_document


async def build_document_search_graph(checkpointer: BaseCheckpointSaver):
    workflow = StateGraph(AgentState)

    workflow.add_node("agent", document_agent_node)
    workflow.add_node("tools", ToolNode([search_document]))

    workflow.set_entry_point("agent")

    workflow.add_conditional_edges(
        "agent",
        tools_condition,
        {
            "tools": "tools",
            END: END,
        },
    )
    workflow.add_edge("tools", "agent")

    return workflow.compile(checkpointer=checkpointer)
