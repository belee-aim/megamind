import pytest
from unittest.mock import AsyncMock, patch
from megamind.graph.workflows.megamind_graph import build_megamind_graph


@pytest.mark.asyncio
async def test_graph_structure():
    """Test that the graph is built with Deep Agent node."""
    with patch(
        "megamind.graph.workflows.megamind_graph.client_manager"
    ) as mock_manager:
        mock_manager.get_client.return_value.get_tools = AsyncMock(return_value=[])
        mock_manager.initialize_client = lambda: None

        app = await build_megamind_graph()

        # Check Deep Agent node exists
        assert "deep_agent" in app.nodes

        # Check knowledge capture node exists
        assert "knowledge_capture_node" in app.nodes

        # Old nodes should NOT exist
        assert "orchestrator_node" not in app.nodes
        assert "planner_node" not in app.nodes
        assert "synthesizer_node" not in app.nodes
        assert "business_process_analyst" not in app.nodes


@pytest.mark.asyncio
async def test_deep_agent_graph_imports():
    """Test that deep_agent_graph module imports correctly."""
    from megamind.graph.workflows.deep_agent_graph import (
        build_deep_agent_graph,
        create_megamind_deep_agent,
        ORCHESTRATOR_PROMPT,
        SPECIALIST_PROMPTS,
    )

    # Verify prompts are defined
    assert "5W3H1R" in ORCHESTRATOR_PROMPT
    assert "business_process" in SPECIALIST_PROMPTS
    assert "workflow" in SPECIALIST_PROMPTS
    assert "report" in SPECIALIST_PROMPTS
    assert "system" in SPECIALIST_PROMPTS
    assert "transaction" in SPECIALIST_PROMPTS


@pytest.mark.asyncio
async def test_tool_utils():
    """Test that tool utilities work correctly."""
    from megamind.graph.utils.tool_utils import (
        SPECIALIST_TOOL_CONFIGS,
        get_local_tools_for_specialist,
    )

    # Check all specialists are configured
    assert "business_process" in SPECIALIST_TOOL_CONFIGS
    assert "workflow" in SPECIALIST_TOOL_CONFIGS
    assert "report" in SPECIALIST_TOOL_CONFIGS
    assert "system" in SPECIALIST_TOOL_CONFIGS
    assert "transaction" in SPECIALIST_TOOL_CONFIGS

    # Check MCP tools are defined for each
    for specialist, config in SPECIALIST_TOOL_CONFIGS.items():
        assert "mcp_tools" in config
        assert isinstance(config["mcp_tools"], list)
