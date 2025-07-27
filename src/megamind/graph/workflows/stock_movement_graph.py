"""
Stock Movement Graph - Intelligent Single-Node Workflow
Smart stock movement processing that only requires item code and quantity from user.
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from megamind.clients.manager import client_manager
from megamind.configuration import Configuration
from megamind.graph.states import StockMovementState

from ..nodes.stock_movement.smart_stock_movement_node import smart_stock_movement_node


async def build_stock_movement_graph(checkpointer: AsyncPostgresSaver = None):
    """
    Builds the stock movement workflow using intelligent single-node approach.
    
    ARCHITECTURE:
    ┌─────────────────────────────────────────────────┐
    │         smart_stock_movement_node               │
    │  ├─ Extract item + quantity from user input     │
    │  ├─ Auto-populate all required fields           │
    │  ├─ Validate item exists via MCP                │
    │  ├─ Create Stock Entry via MCP                  │
    │  └─ Return formatted success message            │
    └─────────────────────────────────────────────────┘
    
    FEATURES:
    - Only asks for item code and quantity
    - Auto-warehouse selection  
    - Enhanced error handling
    - Mongolian language support
    - Smart item search (exact + fuzzy)
    """
    client_manager.initialize_client()
    workflow = StateGraph(StockMovementState, config_schema=Configuration)

    # Add the smart node that handles everything
    workflow.add_node("smart_stock_movement_node", smart_stock_movement_node)

    # Set entry point to the smart node
    workflow.set_entry_point("smart_stock_movement_node")

    # The smart node handles everything and goes directly to END
    workflow.add_edge("smart_stock_movement_node", END)

    # Compile the graph
    app = workflow.compile(checkpointer=checkpointer)
    return app
