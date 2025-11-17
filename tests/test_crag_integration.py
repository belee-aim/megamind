"""
Integration tests for CRAG (Corrective RAG) functionality.

These tests demonstrate how CRAG automatically recovers from operation failures
by detecting errors, retrieving corrective knowledge, and retrying operations.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage

from megamind.graph.nodes.corrective_rag_node import (
    _detect_error,
    _extract_doctype_from_context,
    _generate_corrective_query,
    corrective_rag_node,
    MAX_CORRECTION_ATTEMPTS,
)
from megamind.graph.states import AgentState

# Configure pytest to use anyio for async tests
pytestmark = pytest.mark.anyio(backends=["asyncio"])


class TestErrorDetection:
    """Test error detection in tool results."""

    def test_detect_validation_error(self):
        """Should detect validation errors in tool messages."""
        tool_msg = ToolMessage(
            content="Error: Validation failed. Missing required field: delivery_date",
            tool_call_id="test_123",
        )

        has_error, description = _detect_error(tool_msg)
        assert has_error is True
        assert "validation" in description.lower()
        assert "required field" in description.lower()

    def test_detect_missing_field_error(self):
        """Should detect missing field errors."""
        tool_msg = ToolMessage(
            content="Operation failed: The field 'customer' is required but was not provided",
            tool_call_id="test_123",
        )

        has_error, description = _detect_error(tool_msg)
        assert has_error is True
        assert "required" in description.lower()

    def test_no_error_in_success_message(self):
        """Should not detect error in successful operations."""
        tool_msg = ToolMessage(
            content="Sales Order SO-00123 created successfully",
            tool_call_id="test_123",
        )

        has_error, description = _detect_error(tool_msg)
        assert has_error is False
        assert description is None

    def test_detect_unauthorized_error(self):
        """Should detect authorization errors."""
        tool_msg = ToolMessage(
            content="Error: Unauthorized access to Sales Order",
            tool_call_id="test_123",
        )

        has_error, description = _detect_error(tool_msg)
        assert has_error is True
        assert "unauthorized" in description.lower()


class TestDoctypeExtraction:
    """Test DocType extraction from message context."""

    def test_extract_from_tool_name(self):
        """Should extract DocType from tool call name."""
        messages = [
            HumanMessage(content="Create a sales order"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "create_sales_order",
                        "args": {"customer": "Test"},
                        "id": "call_123",
                    }
                ],
            ),
        ]

        doctype = _extract_doctype_from_context(messages)
        assert doctype == "Sales Order"

    def test_extract_from_args(self):
        """Should extract DocType from tool call arguments."""
        messages = [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "get_doc",
                        "args": {"doctype": "Payment Entry"},
                        "id": "call_123",
                    }
                ],
            ),
        ]

        doctype = _extract_doctype_from_context(messages)
        assert doctype == "Payment Entry"

    def test_no_doctype_found(self):
        """Should return None when no DocType can be extracted."""
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!"),
        ]

        doctype = _extract_doctype_from_context(messages)
        assert doctype is None


class TestCorrectiveQueryGeneration:
    """Test corrective query generation."""

    async def test_generate_query_with_doctype(self):
        """Should generate targeted query when DocType is known."""
        with patch(
            "megamind.graph.nodes.corrective_rag_node.ChatGoogleGenerativeAI"
        ) as mock_llm:
            mock_response = Mock()
            mock_response.content = "Sales Order required fields and validation rules for creation"

            mock_instance = AsyncMock()
            mock_instance.ainvoke.return_value = mock_response
            mock_llm.return_value = mock_instance

            query = await _generate_corrective_query(
                error_description="Missing required field: delivery_date",
                tool_name="create_sales_order",
                doctype="Sales Order",
                original_messages=[],
            )

            assert "sales order" in query.lower()
            assert "required" in query.lower()

    async def test_fallback_query_generation(self):
        """Should generate fallback query on error."""
        with patch(
            "megamind.graph.nodes.corrective_rag_node.ChatGoogleGenerativeAI"
        ) as mock_llm:
            mock_llm.side_effect = Exception("LLM unavailable")

            query = await _generate_corrective_query(
                error_description="Some error",
                tool_name="create_doc",
                doctype="Sales Order",
                original_messages=[],
            )

            # Should fall back to simple query
            assert "sales order" in query.lower()
            assert "required" in query.lower() or "validation" in query.lower()


class TestCRAGNode:
    """Test the main CRAG node logic."""

    async def test_max_attempts_exceeded(self):
        """Should stop correction after max attempts."""
        state: AgentState = {
            "messages": [],
            "correction_attempts": MAX_CORRECTION_ATTEMPTS,
            "access_token": None,
            "user_consent_response": None,
            "validation_context": None,
            "workflow_state": None,
            "performance_metrics": None,
            "last_error_context": None,
            "is_correction_mode": None,
        }

        result = await corrective_rag_node(state, None)

        assert result["correction_attempts"] == MAX_CORRECTION_ATTEMPTS
        assert result["is_correction_mode"] is False

    async def test_no_tool_message(self):
        """Should pass through when no tool message exists."""
        state: AgentState = {
            "messages": [
                HumanMessage(content="Hello"),
                AIMessage(content="Hi!"),
            ],
            "correction_attempts": 0,
            "access_token": None,
            "user_consent_response": None,
            "validation_context": None,
            "workflow_state": None,
            "performance_metrics": None,
            "last_error_context": None,
            "is_correction_mode": None,
        }

        result = await corrective_rag_node(state, None)

        assert result["is_correction_mode"] is False

    async def test_skip_knowledge_tools(self):
        """Should skip CRAG for knowledge search tools."""
        state: AgentState = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "search_erpnext_knowledge",
                            "args": {"query": "test"},
                            "id": "call_123",
                        }
                    ],
                ),
                ToolMessage(
                    content="No results found",
                    tool_call_id="call_123",
                ),
            ],
            "correction_attempts": 0,
            "access_token": None,
            "user_consent_response": None,
            "validation_context": None,
            "workflow_state": None,
            "performance_metrics": None,
            "last_error_context": None,
            "is_correction_mode": None,
        }

        result = await corrective_rag_node(state, None)

        assert result["is_correction_mode"] is False

    async def test_successful_operation_resets_attempts(self):
        """Should reset correction attempts on successful operation."""
        state: AgentState = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "create_sales_order",
                            "args": {"customer": "Test"},
                            "id": "call_123",
                        }
                    ],
                ),
                ToolMessage(
                    content="Sales Order SO-00123 created successfully",
                    tool_call_id="call_123",
                ),
            ],
            "correction_attempts": 1,  # Previous attempt
            "access_token": None,
            "user_consent_response": None,
            "validation_context": None,
            "workflow_state": None,
            "performance_metrics": None,
            "last_error_context": None,
            "is_correction_mode": True,
        }

        result = await corrective_rag_node(state, None)

        assert result["correction_attempts"] == 0  # Reset
        assert result["is_correction_mode"] is False
        assert result["last_error_context"] is None


class TestCRAGIntegration:
    """Integration tests for CRAG workflow."""

    async def test_full_correction_flow(self):
        """Test complete CRAG flow from error detection to correction."""
        with patch(
            "megamind.graph.nodes.corrective_rag_node.TitanClient"
        ) as mock_titan, patch(
            "megamind.graph.nodes.corrective_rag_node.ChatGoogleGenerativeAI"
        ) as mock_llm:

            # Mock LLM for query generation
            mock_response = Mock()
            mock_response.content = "Sales Order required fields for creation"
            mock_llm_instance = AsyncMock()
            mock_llm_instance.ainvoke.return_value = mock_response
            mock_llm.return_value = mock_llm_instance

            # Mock Titan knowledge retrieval
            mock_titan_instance = AsyncMock()
            mock_titan_instance.search_knowledge.return_value = [
                {
                    "title": "Sales Order Required Fields",
                    "content": "Required: customer, delivery_date, items",
                    "summary": "Schema for Sales Order creation",
                    "content_type": "schema",
                    "doctype_name": "Sales Order",
                    "similarity": 0.95,
                }
            ]
            mock_titan.return_value = mock_titan_instance

            # State with error
            state: AgentState = {
                "messages": [
                    HumanMessage(content="Create sales order for ABC Corp"),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "create_sales_order",
                                "args": {"customer": "ABC Corp"},
                                "id": "call_123",
                            }
                        ],
                    ),
                    ToolMessage(
                        content="Error: Missing required field: delivery_date",
                        tool_call_id="call_123",
                    ),
                ],
                "correction_attempts": 0,
                "access_token": None,
                "user_consent_response": None,
                "validation_context": None,
                "workflow_state": None,
                "performance_metrics": None,
                "last_error_context": None,
                "is_correction_mode": None,
            }

            result = await corrective_rag_node(state, None)

            # Verify correction was triggered
            assert result["correction_attempts"] == 1
            assert result["is_correction_mode"] is True
            assert result["last_error_context"] is not None
            assert result["last_error_context"]["doctype"] == "Sales Order"
            assert "delivery_date" in result["last_error_context"]["error_description"]

            # Verify correction message was added
            assert "messages" in result
            assert len(result["messages"]) > 0
            correction_msg = result["messages"][0]
            # Verify it's a SystemMessage (internal guidance for LLM)
            assert isinstance(correction_msg, SystemMessage)
            assert "CORRECTION MODE" in correction_msg.content
            assert "delivery_date" in correction_msg.content.lower()
