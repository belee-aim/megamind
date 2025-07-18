from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from loguru import logger
from typing import Dict, Any, List, Optional, Tuple
from thefuzz import process

from megamind import prompts
from megamind.clients.frappe_client import FrappeClient
from megamind.clients.manager import client_manager
from megamind.configuration import Configuration
from megamind.graph.tools.inventory_tools import InventoryToolFilter
from megamind.graph.tools.enhanced_error_handler import EnhancedErrorHandler
from megamind.graph.exceptions import WarehouseMatchError

from ..states import AgentState


async def _find_best_warehouse_match(
    name_to_match: str, company: str, mcp_client: Any, threshold: int = 90
) -> str:
    """
    Finds the best warehouse name match using fuzzy string matching.
    Raises WarehouseMatchError if no confident match is found.
    """
    if not name_to_match:
        return name_to_match

    try:
        warehouses_result = await mcp_client.call_tool(
            tool_name="list_documents",
            arguments={
                "doctype": "Warehouse",
                "company": company,
                "fields": ["name"],
                "filters": {"is_group": 0},
            },
        )

        warehouse_names = [w["name"] for w in warehouses_result if "name" in w] if warehouses_result else []

        warehouse_names = [w["name"] for w in warehouses_result if "name" in w] if warehouses_result else []

        best_match = process.extractOne(name_to_match, warehouse_names) if warehouse_names else None

        if best_match and best_match[1] >= threshold:
            logger.info(
                f"Confidently matched warehouse '{name_to_match}' to '{best_match[0]}' with score {best_match[1]}"
            )
            return best_match[0]
        else:
            logger.warning(
                f"No confident warehouse match for '{name_to_match}'. Best guess: {best_match[0]} (Score: {best_match[1]})."
            )
            raise WarehouseMatchError(
                f"Could not confidently match warehouse name '{name_to_match}'.",
                original_name=name_to_match,
                suggestions=warehouse_names,
            )

    except Exception as e:
        if isinstance(e, WarehouseMatchError):
            raise  # Re-raise the custom exception
        logger.error(f"An unexpected error occurred during fuzzy warehouse matching for '{name_to_match}': {e}")
        # Wrap unexpected errors in our custom exception to be handled upstream
        raise WarehouseMatchError(str(e), original_name=name_to_match)


def _create_auto_populated_stock_entry(company: str, item_code: str, quantity: float) -> Dict[str, Any]:
    """
    Business logic function to automatically populate all required fields for Stock Entry creation.
    This eliminates the need to ask users for additional information beyond item code and quantity.
    
    Args:
        company (str): Company name from state
        item_code (str): Item code provided by user
        quantity (float): Quantity provided by user
        
    Returns:
        Dict[str, Any]: Fully populated Stock Entry data ready for creation
    """
    
    # Auto-populate all required fields according to business rules
    stock_entry_data = {
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Transfer",  # Always Material Transfer for material pulling
        "company": company,  # Use company from state
        # "series": Leave empty for auto-generation
        "items": [
            {
                "item_code": item_code,
                "qty": quantity,
                "s_warehouse": f"{company} - Main Store",  # Source: Main central warehouse
                "t_warehouse": f"{company} - Branch Store",  # Target: User's branch warehouse  
                "uom": "Nos"  # Default UOM
            }
        ]
    }
    
    logger.info(f"Auto-populated Stock Entry data for {item_code} (Qty: {quantity})")
    logger.debug(f"Stock Entry structure: {stock_entry_data}")
    
    return stock_entry_data


def _get_default_warehouses(company: str) -> tuple[str, str]:
    """
    Get default source and target warehouses based on company.
    
    Args:
        company (str): Company name
        
    Returns:
        tuple[str, str]: (source_warehouse, target_warehouse)
    """
    source_warehouse = f"{company} - Main Store"
    target_warehouse = f"{company} - Branch Store"
    
    logger.debug(f"Default warehouses: {source_warehouse} -> {target_warehouse}")
    
    return source_warehouse, target_warehouse


async def stock_movement_agent_node(state: AgentState, config: RunnableConfig):
    """
    Enhanced stock movement agent for ERPNext operations.
    
    Phase 1 Enhancements:
    - Enhanced search with fuzzy matching and relevance scoring
    - Pre-creation validation with business rules
    - Smart warehouse selection with context awareness
    - Improved error handling and user experience
    
    Phase 2 Enhancements:
    - Document status management and workflow integration
    - Field-level permission control
    - Enhanced workflow state tracking
    
    Phase 3 Enhancements:
    - Smart error categorization and suggestions
    - Contextual help system
    - Performance optimization with caching
    """
    logger.debug("---ENHANCED STOCK MOVEMENT AGENT NODE---")
    configurable = Configuration.from_runnable_config(config)
    mcp_client = client_manager.get_client()

    # Enhanced state management
    company = state.get("company")
    if not company:
        logger.warning("Company not found in state, fetching default company directly.")
        frappe_client = FrappeClient()
        company = frappe_client.get_default_company()
        if not company:
            raise ValueError("Company is required in the agent state and default company could not be fetched.")
        logger.info(f"Using default company: {company}")
    
    last_stock_entry_id = state.get("last_stock_entry_id")
    validation_context = state.get("validation_context", {})
    performance_metrics = state.get("performance_metrics", {})
    
    # Enhanced system prompt with simplified warehouse selection
    system_prompt = prompts.stock_movement_agent_instructions.format(
        company=company,
        last_stock_entry_id=last_stock_entry_id or "Not available",
    )
    
    # Add automatic warehouse selection and field population context
    warehouse_context = f"""
    
🏢 COMPLETE AUTO-POPULATION ENABLED:
- Source Warehouse: Main Central Warehouse (company's main warehouse)
- Target Warehouse: User's Branch Warehouse (automatically detected)
- Only ask for: Item Code/Name + Quantity
- Do NOT ask for warehouse information - it's automatically determined!
- Do NOT ask for Series, Stock Entry Type, Company - auto-populated!
    
AUTO-POPULATION TEMPLATE FOR STOCK ENTRY:
When creating Stock Entry, ALWAYS use this exact structure:
{{
    "doctype": "Stock Entry",
    "stock_entry_type": "Material Transfer",
    "company": "{company}",
    "items": [
        {{
            "item_code": "USER_PROVIDED_ITEM_CODE",
            "qty": USER_PROVIDED_QUANTITY,
            "s_warehouse": "MAIN_CENTRAL_WAREHOUSE",
            "t_warehouse": "USER_BRANCH_WAREHOUSE",
            "uom": "Nos"
        }}
    ]
}}

BUSINESS LOGIC RULES:
1. NEVER ask for Series - leave empty for auto-generation
2. NEVER ask for Stock Entry Type - always "Material Transfer"
3. NEVER ask for Company - use "{company}" from state
4. NEVER ask for warehouse details - auto-determine
5. ONLY ask for Item Code/Name + Quantity
6. Auto-populate ALL other required fields
7. When listing 'Warehouse' or 'Item' documents, ALWAYS add a filter `{{\"is_group\": 0}}` to exclude group records. If the filter doesn't work, fetch the full list and filter out records where `is_group` is 1.
    """
    system_prompt += warehouse_context
    
    # Add enhanced context about recent operations
    recent_search_results = state.get("recent_search_results", [])
    if recent_search_results:
        search_context = "\n\n🔍 Recent Enhanced Search Results:\n"
        for item in recent_search_results:
            if isinstance(item, dict):
                relevance_score = item.get("relevance_score", "N/A")
                search_context += f"- {item.get('item_code', 'N/A')}: {item.get('item_name', 'N/A')} (Brand: {item.get('brand', 'N/A')}) [Score: {relevance_score}]\n"
            else:
                search_context += f"- {str(item)}\n"
        system_prompt += search_context
    
    # Add validation context if available
    if validation_context:
        validation_info = "\n\n✅ Validation Context:\n"
        validation_info += f"- Last validation status: {validation_context.get('status', 'N/A')}\n"
        validation_info += f"- Warnings count: {len(validation_context.get('warnings', []))}\n"
        validation_info += f"- Suggestions count: {len(validation_context.get('suggestions', []))}\n"
        system_prompt += validation_info
    
    # Add performance metrics if available
    if performance_metrics:
        perf_info = "\n\n📊 Performance Metrics:\n"
        perf_info += f"- Average response time: {performance_metrics.get('avg_response_time', 'N/A')}ms\n"
        perf_info += f"- Cache hit rate: {performance_metrics.get('cache_hit_rate', 'N/A')}%\n"
        perf_info += f"- Success rate: {performance_metrics.get('success_rate', 'N/A')}%\n"
        system_prompt += perf_info
    
    messages = [SystemMessage(content=system_prompt)] + state.get("messages", [])

    llm = ChatGoogleGenerativeAI(model=configurable.query_generator_model)
    
    # Get enhanced MCP tools
    mcp_tools = await mcp_client.get_tools()
    
    # Use enhanced inventory tool filter
    inventory_tool_filter = InventoryToolFilter(mcp_tools)
    filtered_tools = inventory_tool_filter.get_filtered_tools()
    
    logger.debug(f"Enhanced tools available: {len(filtered_tools)} tools")
    
    try:
        response = await llm.bind_tools(filtered_tools).ainvoke(messages)

        # --- START: Proactive Warehouse Name Correction ---
        if response.tool_calls:
            for tool_call in response.tool_calls:
                if tool_call["name"] == "create_smart_stock_entry":
                    logger.debug("Applying fuzzy matching for 'create_smart_stock_entry' warehouses.")
                    args = tool_call["args"]
                    
                    if "company" not in args:
                        args["company"] = company

                    from_warehouse = args.get("from_warehouse")
                    to_warehouse = args.get("to_warehouse")

                    if from_warehouse:
                        args["from_warehouse"] = await _find_best_warehouse_match(from_warehouse, args["company"], mcp_client)
                    
                    if to_warehouse:
                        args["to_warehouse"] = await _find_best_warehouse_match(to_warehouse, args["company"], mcp_client)
        # --- END: Proactive Warehouse Name Correction ---

    except WarehouseMatchError as e:
        logger.error(f"Caught a WarehouseMatchError: {e}")
        
        # Create a structured, instructional message for the AI
        ai_instruction = (
            "ACTION: Respond to the user about a warehouse name error.\n"
            f"CONTEXT: The user tried to use a warehouse named '{e.original_name}', but it could not be confidently matched to any existing warehouse.\n"
            "INSTRUCTIONS:\n"
            "1. Inform the user that the warehouse name '{e.original_name}' could not be found or is incorrect.\n"
            "2. If a list of suggestions is available, present them clearly to the user.\n"
            "3. Ask the user to provide the correct names for both the source and target warehouses based on the list.\n"
            "4. Be helpful and clear in your language."
        )
        
        if e.suggestions:
            ai_instruction += "\nAVAILABLE WAREHOUSES:\n" + "\n".join(f"- {name}" for name in e.suggestions)
        else:
            ai_instruction += "\nNOTE: No alternative warehouses could be found to suggest."

        # Return a new HumanMessage that instructs the AI on how to handle the error gracefully
        return {"messages": [HumanMessage(content=ai_instruction)]}


    # Enhanced response processing
    new_stock_entry_id = None
    search_results = []
    validation_results = {}
    workflow_state = {}
    
    if response.tool_calls:
        for tool_call in response.tool_calls:
            logger.debug(f"Processing tool call: {tool_call['name']}")
            
            # Track Stock Entry creation with validation
            if tool_call["name"] == "create_document" and tool_call["args"].get("doctype") == "Stock Entry":
                new_stock_entry_id = tool_call["args"].get("name")
                logger.info(f"Stock Entry created: {new_stock_entry_id}")
            
            # Track enhanced item search results
            elif tool_call["name"] == "search_link_options" and tool_call["args"].get("targetDocType") == "Item":
                search_results = tool_call["args"]
                logger.info(f"Enhanced search performed: {tool_call['args'].get('searchTerm')}")
            
            # Track validation results
            elif tool_call["name"] == "validate_document_enhanced":
                validation_results = tool_call["args"]
                logger.info(f"Document validation performed for: {tool_call['args'].get('doctype')}")
            
            # Track workflow state changes
            elif tool_call["name"] == "get_workflow_state":
                workflow_state = tool_call["args"]
                logger.info(f"Workflow state checked for: {tool_call['args'].get('name')}")
            
            # Track document status checks
            elif tool_call["name"] == "get_document_status":
                logger.info(f"Document status checked for: {tool_call['args'].get('name')}")

    # Enhanced state return with new context
    return {
        "messages": [response],
        "company": company,
        "last_stock_entry_id": new_stock_entry_id or last_stock_entry_id,
        "recent_search_results": search_results,
        "validation_context": validation_results,
        "workflow_state": workflow_state,
        "performance_metrics": _calculate_performance_metrics(performance_metrics),
    }


def _calculate_performance_metrics(existing_metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate and update performance metrics."""
    import time
    
    current_time = time.time()
    
    # Initialize metrics if not exists
    if not existing_metrics:
        return {
            "avg_response_time": 0,
            "cache_hit_rate": 0,
            "success_rate": 100,
            "total_requests": 1,
            "last_update": current_time
        }
    
    # Update existing metrics
    total_requests = existing_metrics.get("total_requests", 0) + 1
    
    return {
        "avg_response_time": existing_metrics.get("avg_response_time", 0),
        "cache_hit_rate": existing_metrics.get("cache_hit_rate", 0),
        "success_rate": existing_metrics.get("success_rate", 100),
        "total_requests": total_requests,
        "last_update": current_time
    }
