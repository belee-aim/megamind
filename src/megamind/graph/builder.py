from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from megamind.graph.rag_graph import build_rag_graph
from megamind.graph.stock_movement_graph import build_stock_movement_graph
from megamind.graph.nodes.router import router_node

async def build_graph(checkpointer: AsyncPostgresSaver = None, query: str = None):
    """
    Builds and compiles the LangGraph for the agent.
    """
    # a router that decides which graph to use
    if "stock" in query.lower() or "movement" in query.lower():
        return await build_stock_movement_graph(checkpointer)
    else:
        return await build_rag_graph(checkpointer)
