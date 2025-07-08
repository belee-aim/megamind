from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from loguru import logger

from megamind import prompts
from megamind.clients.manager import client_manager
from megamind.configuration import Configuration
from megamind.graph.tools.inventory_tools import InventoryToolFilter

from ..states import AgentState


async def stock_movement_agent_node(state: AgentState, config: RunnableConfig):
    """
    Specialized agent for handling stock movement operations in ERPNext.
    Focuses purely on inventory transfers, stock movements, Stock Entry, and Stock Reconciliation.
    Only uses ERPNext MCP tools - no document retrieval functionality.
    Enhanced with flexible item search capabilities (name, brand, description).
    """
    logger.debug("---STOCK MOVEMENT AGENT NODE---")
    configurable = Configuration.from_runnable_config(config)
    mcp_client = client_manager.get_client()

    # No document context needed - this agent only handles ERPNext operations
    company = state.get("company")
    if not company:
        raise ValueError("Company is required in the agent state.")
    last_stock_entry_id = state.get("last_stock_entry_id")
    
    # Enhanced system prompt with flexible search capabilities
    system_prompt = prompts.stock_movement_agent_instructions.format(
        company=company,
        last_stock_entry_id=last_stock_entry_id or "Not available",
    )
    
    # Add context about recent search results if available
    recent_search_results = state.get("recent_search_results", [])
    if recent_search_results:
        search_context = "\n\nRecent Item Search Results:\n"
        for item in recent_search_results:
            search_context += f"- {item.get('item_code', 'N/A')}: {item.get('item_name', 'N/A')} (Brand: {item.get('brand', 'N/A')})\n"
        system_prompt += search_context
    
    messages = [SystemMessage(content=system_prompt)] + state.get("messages", [])

    llm = ChatGoogleGenerativeAI(model=configurable.query_generator_model)
    # Only use ERPNext MCP tools - no frappe_retriever
    mcp_tools = await mcp_client.get_tools()
    
    # Filter tools to only include inventory-related operations
    inventory_tool_filter = InventoryToolFilter(mcp_tools)
    filtered_tools = inventory_tool_filter.get_filtered_tools()
    
    response = await llm.bind_tools(filtered_tools).ainvoke(messages)

    # Extract the new stock entry ID from the response, if available
    new_stock_entry_id = None
    search_results = []
    
    if response.tool_calls:
        for tool_call in response.tool_calls:
            # Track Stock Entry creation
            if tool_call["name"] == "create_document" and tool_call["args"].get("doctype") == "Stock Entry":
                new_stock_entry_id = tool_call["args"].get("name")
            
            # Track Item search results for context
            elif tool_call["name"] == "list_documents" and tool_call["args"].get("doctype") == "Item":
                # Store search parameters for potential future use
                search_results = tool_call["args"].get("filters", [])

    return {
        "messages": [response],
        "company": company,
        "last_stock_entry_id": new_stock_entry_id or last_stock_entry_id,
        "recent_search_results": search_results,
    }
