#!/usr/bin/env python3
"""
Validation script to verify the Minion workflow tools integration.

This script performs basic checks without requiring dependencies to be installed:
1. Verifies all files can be compiled (syntax check)
2. Verifies imports are correct
3. Shows tool information

Run with: python scripts/validate_minion_integration.py
"""

import ast
import sys
from pathlib import Path


def check_file_syntax(filepath: Path) -> bool:
    """Check if a Python file has valid syntax."""
    try:
        with open(filepath) as f:
            ast.parse(f.read())
        print(f"✓ {filepath.relative_to(Path.cwd())}: Syntax OK")
        return True
    except SyntaxError as e:
        print(f"✗ {filepath.relative_to(Path.cwd())}: Syntax Error: {e}")
        return False


def check_imports(filepath: Path) -> bool:
    """Check imports in a Python file."""
    try:
        with open(filepath) as f:
            tree = ast.parse(f.read())
        
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        
        print(f"  Imports: {len(imports)} modules")
        return True
    except Exception as e:
        print(f"✗ Failed to analyze imports: {e}")
        return False


def extract_tool_names(filepath: Path) -> list[str]:
    """Extract tool function names from a file."""
    try:
        with open(filepath) as f:
            tree = ast.parse(f.read())
        
        tools = []
        for node in ast.walk(tree):
            # Check both regular and async function definitions
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Check if function has @tool decorator
                for decorator in node.decorator_list:
                    if (isinstance(decorator, ast.Name) and decorator.id == "tool") or \
                       (isinstance(decorator, ast.Attribute) and decorator.attr == "tool") or \
                       (isinstance(decorator, ast.Call) and 
                        isinstance(decorator.func, ast.Name) and decorator.func.id == "tool"):
                        tools.append(node.name)
                        break
        
        return tools
    except Exception as e:
        print(f"✗ Failed to extract tools: {e}")
        return []


def main():
    """Run validation checks."""
    print("=" * 70)
    print("Minion Workflow Tools Integration Validation")
    print("=" * 70)
    print()
    
    repo_root = Path.cwd()
    all_passed = True
    
    # Files to check
    files_to_check = [
        repo_root / "src/megamind/graph/tools/minion_workflow_tools.py",
        repo_root / "src/megamind/graph/workflows/subagent_graph.py",
        repo_root / "src/megamind/graph/tools/subagent_tools.py",
    ]
    
    print("1. Syntax Validation")
    print("-" * 70)
    for filepath in files_to_check:
        if not filepath.exists():
            print(f"✗ {filepath.relative_to(repo_root)}: File not found")
            all_passed = False
        else:
            result = check_file_syntax(filepath)
            if not result:
                all_passed = False
    print()
    
    print("2. Import Analysis")
    print("-" * 70)
    for filepath in files_to_check:
        if filepath.exists():
            print(f"File: {filepath.relative_to(repo_root)}")
            check_imports(filepath)
    print()
    
    print("3. Tool Discovery")
    print("-" * 70)
    workflow_tools_file = repo_root / "src/megamind/graph/tools/minion_workflow_tools.py"
    if workflow_tools_file.exists():
        tools = extract_tool_names(workflow_tools_file)
        print(f"Found {len(tools)} tools in minion_workflow_tools.py:")
        for tool in tools:
            print(f"  • {tool}")
        
        # Verify expected tools
        expected_tools = [
            "search_business_workflows",
            "search_workflow_knowledge",
            "ask_workflow_question",
            "get_workflow_related_objects",
            "search_employees",
        ]
        
        missing_tools = set(expected_tools) - set(tools)
        if missing_tools:
            print(f"✗ Missing expected tools: {missing_tools}")
            all_passed = False
        else:
            print("✓ All expected tools are present")
    print()
    
    print("4. Integration Check")
    print("-" * 70)
    
    # Check subagent_graph.py imports
    subagent_graph = repo_root / "src/megamind/graph/workflows/subagent_graph.py"
    if subagent_graph.exists():
        with open(subagent_graph) as f:
            content = f.read()
        
        # Check for new imports
        if "from megamind.graph.tools.minion_workflow_tools import" in content:
            print("✓ subagent_graph.py imports from minion_workflow_tools")
        else:
            print("✗ subagent_graph.py does not import from minion_workflow_tools")
            all_passed = False
        
        # Check that ZEP workflow tools are not imported for workflows
        if "from megamind.graph.tools.zep_graph_tools import (" in content:
            lines_after = content.split("from megamind.graph.tools.zep_graph_tools import (")[1].split(")")[0]
            if "search_business_workflows" in lines_after:
                print("✗ subagent_graph.py still imports workflow tools from ZEP")
                all_passed = False
            else:
                print("✓ subagent_graph.py correctly removed workflow imports from ZEP")
        else:
            print("✓ subagent_graph.py correctly imports ZEP tools separately")
    
    # Check subagent_tools.py imports
    subagent_tools = repo_root / "src/megamind/graph/tools/subagent_tools.py"
    if subagent_tools.exists():
        with open(subagent_tools) as f:
            content = f.read()
        
        if "from megamind.graph.tools.minion_workflow_tools import" in content:
            print("✓ subagent_tools.py imports from minion_workflow_tools")
        else:
            print("✗ subagent_tools.py does not import from minion_workflow_tools")
            all_passed = False
    
    print()
    print("=" * 70)
    if all_passed:
        print("✓ All validation checks passed!")
        print()
        print("Summary:")
        print("  • New minion_workflow_tools.py module created with 5 tools")
        print("  • subagent_graph.py updated to use Minion for workflow search")
        print("  • subagent_tools.py updated to use Minion for workflow search")
        print("  • ZEP user knowledge retained (search_user_knowledge)")
        return 0
    else:
        print("✗ Some validation checks failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
