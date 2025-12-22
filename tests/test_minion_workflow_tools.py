"""
Tests for minion_workflow_tools module.

These tests verify that the new Minion workflow tools are properly
implemented and can be imported and used correctly.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Test imports work correctly
def test_imports():
    """Verify all tools can be imported."""
    from megamind.graph.tools.minion_workflow_tools import (
        search_business_workflows,
        search_workflow_knowledge,
        ask_workflow_question,
        get_workflow_related_objects,
        search_employees,
    )
    
    # Verify tools are callable
    assert callable(search_business_workflows)
    assert callable(search_workflow_knowledge)
    assert callable(ask_workflow_question)
    assert callable(get_workflow_related_objects)
    assert callable(search_employees)


def test_tool_names():
    """Verify tool names are correct."""
    from megamind.graph.tools.minion_workflow_tools import (
        search_business_workflows,
        search_workflow_knowledge,
        ask_workflow_question,
        get_workflow_related_objects,
        search_employees,
    )
    
    assert search_business_workflows.name == "search_business_workflows"
    assert search_workflow_knowledge.name == "search_workflow_knowledge"
    assert ask_workflow_question.name == "ask_workflow_question"
    assert get_workflow_related_objects.name == "get_workflow_related_objects"
    assert search_employees.name == "search_employees"


@pytest.mark.asyncio
async def test_search_business_workflows():
    """Test search_business_workflows calls correct Minion API."""
    from megamind.graph.tools.minion_workflow_tools import search_business_workflows
    
    mock_result = {"results": [{"id": "1", "name": "Test Workflow"}]}
    
    with patch("megamind.graph.tools.minion_workflow_tools._get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(return_value=mock_result)
        mock_get_client.return_value = mock_client
        
        result = await search_business_workflows.ainvoke({"query": "test query"})
        
        # Verify client method was called with correct parameters
        mock_client.search.assert_called_once_with(
            query="test query",
            object_types=["Workflow", "BusinessProcess", "ProcessStep"],
            limit=10,
        )
        
        # Verify result contains expected data
        assert "Test Workflow" in result


@pytest.mark.asyncio
async def test_search_workflow_knowledge():
    """Test search_workflow_knowledge with custom object types."""
    from megamind.graph.tools.minion_workflow_tools import search_workflow_knowledge
    
    mock_result = {"results": [{"id": "1", "name": "Test Knowledge"}]}
    
    with patch("megamind.graph.tools.minion_workflow_tools._get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(return_value=mock_result)
        mock_get_client.return_value = mock_client
        
        result = await search_workflow_knowledge.ainvoke({
            "query": "test query",
            "object_types": ["Role", "Policy"],
            "limit": 5,
        })
        
        # Verify client method was called with correct parameters
        mock_client.search.assert_called_once_with(
            query="test query",
            object_types=["Role", "Policy"],
            limit=5,
        )
        
        assert "Test Knowledge" in result


@pytest.mark.asyncio
async def test_ask_workflow_question():
    """Test ask_workflow_question calls Minion ask API."""
    from megamind.graph.tools.minion_workflow_tools import ask_workflow_question
    
    mock_result = {"answer": "This is the answer"}
    
    with patch("megamind.graph.tools.minion_workflow_tools._get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.ask = AsyncMock(return_value=mock_result)
        mock_get_client.return_value = mock_client
        
        result = await ask_workflow_question.ainvoke({"question": "What is the workflow?"})
        
        # Verify client method was called
        mock_client.ask.assert_called_once_with(question="What is the workflow?")
        
        assert "answer" in result


@pytest.mark.asyncio
async def test_get_workflow_related_objects():
    """Test get_workflow_related_objects calls Minion get_related API."""
    from megamind.graph.tools.minion_workflow_tools import get_workflow_related_objects
    
    mock_result = {"related": [{"id": "1", "type": "ProcessStep"}]}
    
    with patch("megamind.graph.tools.minion_workflow_tools._get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.get_related = AsyncMock(return_value=mock_result)
        mock_get_client.return_value = mock_client
        
        result = await get_workflow_related_objects.ainvoke({
            "object_type": "Workflow",
            "object_id": "WF-001",
            "direction": "both",
            "max_depth": 2,
        })
        
        # Verify client method was called with correct parameters
        mock_client.get_related.assert_called_once_with(
            object_type="Workflow",
            object_id="WF-001",
            direction="both",
            max_depth=2,
        )
        
        assert "ProcessStep" in result


@pytest.mark.asyncio
async def test_search_employees():
    """Test search_employees calls correct Minion API with employee object types."""
    from megamind.graph.tools.minion_workflow_tools import search_employees
    
    mock_result = {"results": [{"id": "1", "name": "John Doe", "role": "Manager"}]}
    
    with patch("megamind.graph.tools.minion_workflow_tools._get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(return_value=mock_result)
        mock_get_client.return_value = mock_client
        
        result = await search_employees.ainvoke({"query": "finance manager"})
        
        # Verify client method was called with correct parameters
        mock_client.search.assert_called_once_with(
            query="finance manager",
            object_types=["User", "Employee", "Department", "Role"],
            limit=10,
        )
        
        assert "John Doe" in result
        assert "Manager" in result


@pytest.mark.asyncio
async def test_error_handling():
    """Test that tools handle errors gracefully."""
    from megamind.graph.tools.minion_workflow_tools import search_business_workflows
    
    with patch("megamind.graph.tools.minion_workflow_tools._get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(side_effect=Exception("Connection error"))
        mock_get_client.return_value = mock_client
        
        result = await search_business_workflows.ainvoke({"query": "test"})
        
        # Verify error message is returned
        assert "error" in result.lower()
        assert "connection error" in result.lower()
        assert "minion service may be unavailable" in result.lower()


def test_subagent_graph_imports():
    """Verify subagent_graph imports the new tools correctly."""
    from megamind.graph.workflows import subagent_graph
    
    # Verify the module has the expected functions
    assert hasattr(subagent_graph, "get_orchestrator_tools")
    assert hasattr(subagent_graph, "get_knowledge_tools")
    
    # Verify tools are included in the lists
    orchestrator_tools = subagent_graph.get_orchestrator_tools()
    knowledge_tools = subagent_graph.get_knowledge_tools()
    
    # Check that workflow tools are present
    tool_names_orchestrator = [t.name for t in orchestrator_tools]
    tool_names_knowledge = [t.name for t in knowledge_tools]
    
    assert "search_business_workflows" in tool_names_orchestrator
    assert "search_employees" in tool_names_orchestrator
    assert "search_business_workflows" in tool_names_knowledge
    assert "search_workflow_knowledge" in tool_names_knowledge
    assert "ask_workflow_question" in tool_names_knowledge
    assert "get_workflow_related_objects" in tool_names_knowledge
    assert "search_employees" in tool_names_knowledge
