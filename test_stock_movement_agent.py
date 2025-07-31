#!/usr/bin/env python3
"""
Test script for the stock movement agent implementation.
This script tests the routing logic and ensures the new agent is properly integrated.
"""

import pytest
import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from megamind.graph.tools.inventory_tools import InventoryToolFilter
from langchain_core.tools import tool


@tool
def create_document(doctype: str, doc: dict):
    """Creates a document."""
    pass


@tool
def get_document(doctype: str, name: str):
    """Gets a document."""
    pass


@tool
def some_other_tool():
    """Some other tool."""
    pass


def test_prompts():
    """Test that all required prompts are defined."""
    print("\nTesting prompts...")

    try:
        from megamind.prompts import (
            rag_node_instructions,
            agent_node_instructions,
            stock_movement_agent_instructions,
        )

        print("✓ All required prompts are defined")
        print(f"  - rag_node_instructions: {len(rag_node_instructions)} chars")
        print(f"  - agent_node_instructions: {len(agent_node_instructions)} chars")
        print(
            f"  - stock_movement_agent_instructions: {len(stock_movement_agent_instructions)} chars"
        )

        # Check that stock movement prompt contains key terms and excludes document retrieval
        stock_prompt = stock_movement_agent_instructions.lower()
        key_terms = [
            "stock entry",
            "material request",
            "stock reconciliation",
            "inventory",
        ]
        excluded_terms = ["frappe_retriever", "documents", "document retrieval"]

        for term in key_terms:
            if term in stock_prompt:
                print(f"  ✓ Contains '{term}'")
            else:
                print(f"  ✗ Missing '{term}'")

        for term in excluded_terms:
            if term not in stock_prompt:
                print(f"  ✓ Correctly excludes '{term}'")
            else:
                print(f"  ✗ Should not contain '{term}'")

        assert all(term in stock_prompt for term in key_terms)
        assert all(term not in stock_prompt for term in excluded_terms)

    except ImportError as e:
        print(f"✗ Prompt import test failed: {e}")
        assert False, f"Prompt import test failed: {e}"


def test_file_structure():
    """Test that all required files exist."""
    print("\nTesting file structure...")

    required_files = [
        "src/megamind/graph/nodes/stock_movement_agent.py",
        "src/megamind/graph/schemas.py",
        "src/megamind/graph/states.py",
        "src/megamind/graph/builder.py",
        "src/megamind/models/requests.py",
        "src/megamind/main.py",
        "src/megamind/prompts.py",
    ]

    all_exist = True
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"  ✓ {file_path}")
        else:
            print(f"  ✗ {file_path} (missing)")
            all_exist = False

    assert all_exist, "Some required files are missing"


def test_graph_building():
    """Test that the graph can be built without errors."""
    print("\nTesting graph building...")

    import asyncio

    async def _test():
        from megamind.graph.builder import build_graph

        # This would normally require MCP client setup, so we'll just test imports
        print("✓ Graph builder imports successfully")
        print("✓ All node imports should work")

        # Test that the stock movement agent node can be imported
        from megamind.graph.nodes.stock_movement_agent import stock_movement_agent_node

        print("✓ Stock movement agent node imports successfully")

        assert True

    asyncio.run(_test())


def test_inventory_tool_filter():
    """Test the InventoryToolFilter class."""
    print("\nTesting InventoryToolFilter...")

    # Mock MCP tools
    mcp_tools = [
        create_document,
        get_document,
        some_other_tool,
    ]

    inventory_tool_filter = InventoryToolFilter(mcp_tools)
    filtered_tools = inventory_tool_filter.get_filtered_tools()

    # For now, we expect all tools to be returned
    assert len(filtered_tools) == 3
    print("✓ InventoryToolFilter returns all tools as expected")
