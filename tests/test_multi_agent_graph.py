import pytest
from unittest.mock import AsyncMock, patch
from megamind.graph.workflows.megamind_graph import build_megamind_graph


@pytest.mark.asyncio
async def test_graph_structure():
    """Test that the graph is built with all required nodes."""
    with patch(
        "megamind.graph.workflows.megamind_graph.client_manager"
    ) as mock_manager:
        mock_manager.get_client.return_value.get_tools = AsyncMock(return_value=[])

        app = await build_megamind_graph()

        # Check core nodes exist
        assert "orchestrator_node" in app.nodes
        assert "planner_node" in app.nodes

        # Check subagent nodes
        assert "semantic_analyst" in app.nodes
        assert "report_analyst" in app.nodes
        assert "system_specialist" in app.nodes


@pytest.mark.asyncio
async def test_orchestrator_structured_output():
    """Test that orchestrator uses structured output."""
    from megamind.graph.nodes.orchestrator import OrchestratorDecision

    # Verify the decision model has required fields
    assert hasattr(OrchestratorDecision, "model_fields")
    assert "action" in OrchestratorDecision.model_fields
    assert "target_specialist" in OrchestratorDecision.model_fields
    assert "response" in OrchestratorDecision.model_fields


@pytest.mark.asyncio
async def test_planner_structured_output():
    """Test that planner uses structured output."""
    from megamind.graph.nodes.planner import ExecutionPlan, PlanStep

    # Verify the plan models
    assert hasattr(ExecutionPlan, "model_fields")
    assert "steps" in ExecutionPlan.model_fields

    assert hasattr(PlanStep, "model_fields")
    assert "specialist" in PlanStep.model_fields
    assert "task" in PlanStep.model_fields
