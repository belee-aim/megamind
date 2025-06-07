from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition # Added tools_condition

from .state import AgentState
from .nodes import generate_node, agent_node # Removed stream_node
from .tools.retriever import get_retriever_tool

def build_graph():
    """
    Builds and compiles the LangGraph for the agent.
    """
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("agent", agent_node) # New agent node
    workflow.add_node("retrieve", ToolNode([get_retriever_tool()])) # ToolNode for retrieval
    workflow.add_node("generate", generate_node) # Generate response node

    workflow.set_entry_point("agent") 

    # Add conditional edge from agent: decide whether to call tool or end
    workflow.add_conditional_edges(
        "agent",
        tools_condition, # Use tools_condition to check for tool calls
        {
            "tools": "retrieve", # If tool calls, go to retrieve (ToolNode)
            END: END, # If no tool calls, end (LLM responded directly)
        },
    )

    # Add edges
    # After retrieve (ToolNode), go to generate
    workflow.add_edge("retrieve", "generate")
    # After generate, end the graph
    workflow.add_edge("generate", END)

    # Compile the graph
    app = workflow.compile()
    return app
