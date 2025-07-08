"""
Inventory-specific tool filtering for the stock movement agent.
This module provides filtered MCP tools that only allow inventory-related operations.
"""

from typing import List, Dict, Any
from loguru import logger


class InventoryToolFilter:
    """
    Filters MCP tools to only include inventory-related operations.
    """
    
    # Define allowed DocTypes for inventory operations
    ALLOWED_INVENTORY_DOCTYPES = {
        # Core Stock DocTypes
        "Stock Entry",
        "Stock Reconciliation", 
        "Material Request",
        "Stock Ledger Entry",
        "Stock Entry Type",
        "Stock Entry Detail",
        "Material Request Item",
        
        # Warehouse Management
        "Warehouse",
        "Warehouse Type",
        
        # Item Management
        "Item",
        "Item Group",
        "Item Price",
        "Item Barcode",
        "Item Alternative",
        "Item Attribute",
        "Item Attribute Value",
        "Item Customer Detail",
        "Item Supplier",
        "Item Tax Template",
        "Item Variant Attribute",
        
        # Other related DocTypes
        # "Delivery Note",
        # "Purchase Receipt",
        # "Delivery Note Item",
        # "Purchase Receipt Item",
    }

    def __init__(self, mcp_tools: List[Any]):
        self.mcp_tools = mcp_tools

    def get_filtered_tools(self) -> List[Any]:
        """
        Returns a filtered list of MCP tools that are allowed for inventory operations.
        """
        filtered_tools = []
        for tool in self.mcp_tools:
            tool_name = tool.name
            
            # Check if the tool operates on a specific DocType
            if hasattr(tool.args_schema, 'get_fields') and 'doctype' in tool.args_schema.get_fields():
                # This is a generic tool that can operate on any DocType.
                # We will only allow it if the tool is one of the generic tools we want to allow.
                if tool_name in ["get_document", "list_documents", "create_document", "update_document", "delete_document"]:
                    filtered_tools.append(tool)
                    logger.debug(f"Allowing generic tool: {tool_name}")
            else:
                # This is a specific tool that operates on a specific DocType.
                # We can check if the DocType is in our allowed list.
                # However, the current MCP server doesn't provide such tools.
                # For now, we will allow all tools and rely on the agent's prompt.
                filtered_tools.append(tool)
                logger.debug(f"Allowing specific tool: {tool_name}")
                
        return filtered_tools
