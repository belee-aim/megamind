#!/usr/bin/env python3
"""
Test the improved extraction for MAM4-BLA-36⅔ type item codes
"""

import sys
sys.path.insert(0, 'src')

from megamind.graph.nodes.stock_movement.smart_stock_movement_node import _fallback_extraction

def test_mam4_extraction():
    """Test extraction for MAM4-BLA-36⅔ type codes"""
    test_cases = [
        {
            "input": "MAM4-BLA-36⅔ бараанаас 10ширхэгийг татаж өгнө үү",
            "expected_item": "MAM4-BLA-36⅔",
            "expected_quantity": 10
        },
        {
            "input": "MAM4-BLA-36⅔ барааг 5 ширхэг шилжүүлнэ үү",
            "expected_item": "MAM4-BLA-36⅔",
            "expected_quantity": 5
        },
        {
            "input": "SKU001 кодтой бараанаа 15 ширхэг",
            "expected_item": "SKU001", 
            "expected_quantity": 15
        }
    ]
    
    print("🧪 Testing improved extraction patterns...")
    
    for i, case in enumerate(test_cases):
        print(f"\n  Test case {i+1}: {case['input']}")
        result = _fallback_extraction(case["input"])
        
        print(f"    Expected: item='{case['expected_item']}', quantity={case['expected_quantity']}")
        print(f"    Got: item='{result['item_code']}', quantity={result['quantity']}")
        
        # Check results
        if result["item_code"] == case["expected_item"] and result["quantity"] == case["expected_quantity"]:
            print(f"    ✅ PASSED")
        else:
            print(f"    ❌ FAILED")
            
    print("\n🎯 Testing complete!")

if __name__ == "__main__":
    test_mam4_extraction()
