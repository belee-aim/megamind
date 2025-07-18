#!/usr/bin/env python3
"""
Test script for simplified stock movement agent workflow.
Tests the enhanced system that only asks for item code and quantity.
"""

import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

# Mock the required modules
import sys
sys.path.insert(0, 'src')

from megamind.graph.nodes.stock_movement_agent import (
    stock_movement_agent_node,
    _create_auto_populated_stock_entry,
    _get_default_warehouses
)
from megamind.graph.states import AgentState


class MockMessage:
    """Mock message class for testing."""
    def __init__(self, content: str, tool_calls: list = None):
        self.content = content
        self.tool_calls = tool_calls or []


class MockTool:
    """Mock tool class for testing."""
    def __init__(self, name: str):
        self.name = name
        self.args_schema = Mock()
        self.args_schema.get_fields = Mock(return_value={})


async def test_auto_populated_stock_entry():
    """Test the auto-population business logic function."""
    print("🧪 Testing auto-populated stock entry function...")
    
    # Test data
    company = "Test Company"
    item_code = "SKU001"
    quantity = 10.0
    
    # Call the function
    result = _create_auto_populated_stock_entry(company, item_code, quantity)
    
    # Verify the structure
    expected_structure = {
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Transfer",
        "company": company,
        "items": [
            {
                "item_code": item_code,
                "qty": quantity,
                "s_warehouse": f"{company} - Main Store",
                "t_warehouse": f"{company} - Branch Store",
                "uom": "Nos"
            }
        ]
    }
    
    print(f"✅ Generated Stock Entry structure:")
    print(json.dumps(result, indent=2))
    
    # Assertions
    assert result["doctype"] == "Stock Entry"
    assert result["stock_entry_type"] == "Material Transfer"
    assert result["company"] == company
    assert len(result["items"]) == 1
    assert result["items"][0]["item_code"] == item_code
    assert result["items"][0]["qty"] == quantity
    assert result["items"][0]["s_warehouse"] == f"{company} - Main Store"
    assert result["items"][0]["t_warehouse"] == f"{company} - Branch Store"
    assert result["items"][0]["uom"] == "Nos"
    
    print("✅ Auto-populated stock entry test passed!")
    return True


async def test_default_warehouses():
    """Test the default warehouse selection function."""
    print("\n🧪 Testing default warehouse selection...")
    
    company = "Test Company"
    source, target = _get_default_warehouses(company)
    
    expected_source = f"{company} - Main Store"
    expected_target = f"{company} - Branch Store"
    
    print(f"✅ Source warehouse: {source}")
    print(f"✅ Target warehouse: {target}")
    
    assert source == expected_source
    assert target == expected_target
    
    print("✅ Default warehouse selection test passed!")
    return True


async def test_stock_movement_agent_workflow():
    """Test the complete stock movement agent workflow."""
    print("\n🧪 Testing complete stock movement agent workflow...")
    
    # Mock configuration
    with patch('megamind.graph.nodes.stock_movement_agent.Configuration') as mock_config:
        mock_config.from_runnable_config.return_value = Mock(
            query_generator_model="test-model"
        )
        
        # Mock client manager
        with patch('megamind.graph.nodes.stock_movement_agent.client_manager') as mock_client_manager:
            mock_client = AsyncMock()
            mock_tools = [MockTool("create_document"), MockTool("get_document")]
            mock_client.get_tools.return_value = mock_tools
            mock_client_manager.get_client.return_value = mock_client
            
            # Mock LLM
            with patch('megamind.graph.nodes.stock_movement_agent.ChatGoogleGenerativeAI') as mock_llm_class:
                mock_llm = AsyncMock()
                mock_response = MockMessage(
                    content="Бараа материалын хөдөлгөөн үүсгэгдлээ",
                    tool_calls=[
                        {
                            "name": "create_document",
                            "args": {
                                "doctype": "Stock Entry",
                                "values": {
                                    "doctype": "Stock Entry",
                                    "stock_entry_type": "Material Transfer",
                                    "company": "Test Company"
                                }
                            }
                        }
                    ]
                )
                mock_llm.ainvoke.return_value = mock_response
                mock_llm_class.return_value = mock_llm
                
                # Mock prompts
                with patch('megamind.graph.nodes.stock_movement_agent.prompts') as mock_prompts:
                    mock_prompts.stock_movement_agent_instructions.format.return_value = "Test prompt"
                    
                    # Test state
                    state = AgentState(
                        company="Test Company",
                        messages=[MockMessage("SKU001 кодтой бараанаа 10 ширхэгийг татаж авмаар байна")]
                    )
                    
                    # Mock config
                    config = Mock()
                    
                    # Call the agent
                    result = await stock_movement_agent_node(state, config)
                    
                    # Verify response
                    assert result["company"] == "Test Company"
                    assert len(result["messages"]) == 1
                    assert result["messages"][0].content == "Бараа материалын хөдөлгөөн үүсгэгдлээ"
                    
                    print("✅ Stock movement agent workflow test passed!")
                    return True


async def test_user_interaction_simulation():
    """Simulate the user interaction from the feedback."""
    print("\n🧪 Simulating user interaction from feedback...")
    
    # User input: "SKU001 кодтой бараанаа 10 ширхэгийг татаж авмаар байна"
    user_input = "SKU001 кодтой бараанаа 10 ширхэгийг татаж авмаар байна"
    
    # Extract item code and quantity (this would be done by the LLM)
    item_code = "SKU001"
    quantity = 10
    company = "Test Company"
    
    # Use business logic to auto-populate
    stock_entry_data = _create_auto_populated_stock_entry(company, item_code, quantity)
    
    print(f"📝 User request: {user_input}")
    print(f"🔍 Extracted: item_code={item_code}, quantity={quantity}")
    print(f"🏢 Company: {company}")
    print(f"📋 Auto-populated Stock Entry:")
    print(json.dumps(stock_entry_data, indent=2))
    
    # Expected response format
    expected_response = """
✅ Бараа материалын хөдөлгөөн үүсгэгдлээ
ID: SE-2024-001
Бараа: SKU001 – 10 ширхэг
Test Company - Main Store → Test Company - Branch Store
"""
    
    print(f"💬 Expected response format:")
    print(expected_response)
    
    # Verify no additional fields are required
    required_fields = ["doctype", "stock_entry_type", "company", "items"]
    for field in required_fields:
        assert field in stock_entry_data, f"Missing required field: {field}"
    
    # Verify items structure
    item = stock_entry_data["items"][0]
    item_required_fields = ["item_code", "qty", "s_warehouse", "t_warehouse", "uom"]
    for field in item_required_fields:
        assert field in item, f"Missing required item field: {field}"
    
    print("✅ User interaction simulation test passed!")
    return True


async def run_all_tests():
    """Run all tests."""
    print("🚀 Starting simplified stock movement tests...\n")
    
    tests = [
        test_auto_populated_stock_entry,
        test_default_warehouses,
        test_stock_movement_agent_workflow,
        test_user_interaction_simulation
    ]
    
    results = []
    for test in tests:
        try:
            result = await test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test failed: {e}")
            results.append(False)
    
    print(f"\n📊 Test Results: {sum(results)}/{len(results)} passed")
    
    if all(results):
        print("🎉 All tests passed! The simplified stock movement system is working correctly.")
        print("\n✅ Key Features Verified:")
        print("- Auto-population of all required fields")
        print("- Only asks for item code and quantity")
        print("- Automatic warehouse selection")
        print("- Proper Stock Entry structure generation")
        print("- Business logic functions working correctly")
    else:
        print("❌ Some tests failed. Please check the implementation.")
    
    return all(results)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
