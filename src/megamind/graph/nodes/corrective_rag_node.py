"""
Corrective RAG Node - Implements CRAG pattern for error recovery.

This node analyzes tool execution results, detects errors, rewrites knowledge queries,
and re-retrieves information to help the agent recover from failures.
"""

import re
from typing import Dict, Any
from langchain_core.messages import ToolMessage, AIMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from loguru import logger

from megamind.clients.titan_client import TitanClient
from megamind.configuration import Configuration
from megamind.graph.states import AgentState


# Maximum correction attempts before giving up
MAX_CORRECTION_ATTEMPTS = 2

# Error patterns to detect in tool results
ERROR_PATTERNS = [
    r"error",
    r"failed",
    r"validation",
    r"required field",
    r"missing",
    r"invalid",
    r"not found",
    r"unauthorized",
    r"forbidden",
    r"cannot",
    r"unable to",
]


def _detect_error(tool_message: ToolMessage) -> tuple[bool, str | None]:
    """
    Analyze a tool message to detect if it contains an error.

    Returns:
        (has_error, error_description)
    """
    if not isinstance(tool_message, ToolMessage):
        return False, None

    content = str(tool_message.content).lower()

    # Check for error patterns
    for pattern in ERROR_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            # Extract a snippet around the error
            match = re.search(f"(.{{0,50}}{pattern}.{{0,100}})", content, re.IGNORECASE)
            if match:
                error_snippet = match.group(0).strip()
                logger.info(f"Error detected: {error_snippet[:100]}")
                return True, error_snippet

    return False, None


def _extract_doctype_from_context(messages: list) -> str | None:
    """
    Try to extract the DocType being operated on from recent messages.
    """
    # Look at the last few AI messages for tool calls
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
            for tool_call in msg.tool_calls:
                tool_name = tool_call.get("name", "")
                args = tool_call.get("args", {})

                # Check if args contain a doctype field first (more reliable)
                if "doctype" in args:
                    return args["doctype"]
                if "doc_type" in args:
                    return args["doc_type"]

                # Check if tool name contains a doctype (e.g., "create_sales_order")
                # Pattern: operation_(doctype_name)
                doctype_match = re.search(r"(?:create_|update_|delete_|get_)([a-z_]+)", tool_name)
                if doctype_match:
                    # Convert snake_case to Title Case
                    doctype = doctype_match.group(1).replace("_", " ").title()
                    return doctype

    return None


async def _generate_corrective_query(
    error_description: str,
    tool_name: str,
    doctype: str | None,
    original_messages: list,
) -> str:
    """
    Use LLM to generate an improved knowledge search query based on the error.
    """
    logger.info(f"Generating corrective query for error: {error_description[:100]}")

    # Build context from recent messages
    recent_context = []
    for msg in original_messages[-3:]:  # Last 3 messages for context
        if isinstance(msg, HumanMessage):
            recent_context.append(f"User: {msg.content}")
        elif isinstance(msg, AIMessage) and msg.content:
            recent_context.append(f"Assistant: {msg.content[:200]}")

    context_str = "\n".join(recent_context)

    prompt = f"""You are an expert at analyzing ERPNext errors and generating targeted knowledge search queries.

# Context
The user attempted an ERPNext operation that failed with an error.

**Recent Conversation:**
{context_str}

**Failed Tool:** {tool_name}
**DocType:** {doctype or "Unknown"}
**Error Message:** {error_description}

# Task
Generate a precise knowledge search query that will retrieve information to fix this error.

Focus on:
1. Required fields that might be missing
2. Validation rules that were violated
3. Correct workflow sequences
4. Field formats and data types
5. Common pitfalls for this operation

# Output Format
Return ONLY the search query text, nothing else. Make it specific and actionable.

# Examples
- "Sales Order required fields and validation rules for creation"
- "Payment Entry mandatory fields and workflow sequence"
- "Stock Entry item table required child fields and formats"

# Your Query:"""

    try:
        config = Configuration()
        llm = ChatGoogleGenerativeAI(
            model=config.query_generator_model,
            temperature=0.3,  # Lower temperature for more focused queries
        )

        response = await llm.ainvoke(prompt)
        query = response.content.strip().strip('"').strip("'")

        logger.info(f"Generated corrective query: {query}")
        return query

    except Exception as e:
        logger.error(f"Error generating corrective query: {e}")
        # Fallback to a simple query
        if doctype:
            return f"{doctype} required fields validation rules and common errors"
        return "ERPNext required fields and validation errors"


async def _retrieve_corrective_knowledge(
    query: str,
    doctype: str | None,
) -> str:
    """
    Retrieve knowledge using the corrected query.
    """
    logger.info(f"Retrieving corrective knowledge for query: {query}")

    try:
        titan_client = TitanClient()

        # Search with higher match count for corrections
        results = await titan_client.search_knowledge(
            query=query,
            doctype_filter=doctype,
            match_count=7,  # More results for corrections
            similarity_threshold=0.6,  # Lower threshold to catch more relevant info
        )

        if not results:
            logger.warning("No corrective knowledge found")
            return ""

        # Format results with emphasis on schemas and required fields
        formatted_parts = [
            "# 🔧 Corrective Knowledge Retrieved",
            f"Found {len(results)} relevant entries to help fix the error:\n",
        ]

        for i, entry in enumerate(results, 1):
            title = entry.get("title", "Untitled")
            content = entry.get("content", "")
            summary = entry.get("summary", "")
            content_type = entry.get("content_type", "")

            formatted_parts.append(f"## {i}. {title}")

            if content_type:
                formatted_parts.append(f"**Type**: {content_type}")

            if summary:
                formatted_parts.append(f"**Summary**: {summary}\n")

            # Truncate content if needed
            if len(content) > 2500:
                content = content[:2500] + "\n\n[Truncated...]"

            formatted_parts.append(content)
            formatted_parts.append("\n---\n")

        result_text = "\n".join(formatted_parts)
        logger.info(f"Retrieved {len(results)} corrective knowledge entries")

        return result_text

    except Exception as e:
        logger.error(f"Error retrieving corrective knowledge: {e}")
        return ""


async def corrective_rag_node(state: AgentState, config) -> Dict[str, Any]:
    """
    CRAG Node: Analyzes tool execution results and provides corrective knowledge when errors are detected.

    Flow:
    1. Check if we've exceeded max correction attempts
    2. Analyze the last tool message for errors
    3. If error detected:
       - Generate improved knowledge query
       - Retrieve corrective knowledge
       - Add correction context to state
    4. Return updated state
    """
    logger.debug("---CRAG NODE---")

    messages = state.get("messages", [])
    correction_attempts = state.get("correction_attempts", 0)

    # Safety check: prevent infinite correction loops
    if correction_attempts >= MAX_CORRECTION_ATTEMPTS:
        logger.warning(f"Max correction attempts ({MAX_CORRECTION_ATTEMPTS}) reached, passing through")
        return {
            "correction_attempts": correction_attempts,
            "is_correction_mode": False,
        }

    # Find the last tool message
    last_tool_message = None
    tool_name = None

    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            last_tool_message = msg
            # Find the corresponding AI message with tool call
            for ai_msg in reversed(messages):
                if isinstance(ai_msg, AIMessage) and hasattr(ai_msg, 'tool_calls') and ai_msg.tool_calls:
                    for tool_call in ai_msg.tool_calls:
                        if tool_call.get("id") == msg.tool_call_id:
                            tool_name = tool_call.get("name")
                            break
                if tool_name:
                    break
            break

    if not last_tool_message:
        logger.debug("No tool message found, passing through")
        return {"is_correction_mode": False}

    # Skip correction for knowledge search tools (they don't fail in the same way)
    if tool_name in ["search_erpnext_knowledge", "get_erpnext_knowledge_by_id"]:
        logger.debug(f"Skipping CRAG for knowledge tool: {tool_name}")
        return {"is_correction_mode": False}

    # Detect error
    has_error, error_description = _detect_error(last_tool_message)

    if not has_error:
        logger.debug("No error detected in tool result")
        return {
            "correction_attempts": 0,  # Reset on success
            "is_correction_mode": False,
            "last_error_context": None,
        }

    # Error detected - initiate correction
    logger.info(f"🔧 CRAG: Error detected in {tool_name}, initiating correction (attempt {correction_attempts + 1}/{MAX_CORRECTION_ATTEMPTS})")

    # Extract doctype from context
    doctype = _extract_doctype_from_context(messages)
    logger.info(f"Extracted DocType: {doctype}")

    # Generate corrective query
    corrective_query = await _generate_corrective_query(
        error_description=error_description,
        tool_name=tool_name or "unknown",
        doctype=doctype,
        original_messages=messages,
    )

    # Retrieve corrective knowledge
    corrective_knowledge = await _retrieve_corrective_knowledge(
        query=corrective_query,
        doctype=doctype,
    )

    # Build correction context
    error_context = {
        "error_description": error_description,
        "failed_tool": tool_name,
        "doctype": doctype,
        "corrective_query": corrective_query,
        "attempt_number": correction_attempts + 1,
    }

    # Add corrective guidance message to help the agent
    correction_message = AIMessage(
        content=f"""🔧 **Correction Mode Activated**

The previous operation failed with an error. I've retrieved additional knowledge to help fix this.

**Error:** {error_description[:200]}
**Failed Operation:** {tool_name}
**DocType:** {doctype or 'Unknown'}

**Corrective Knowledge Retrieved:**
{corrective_knowledge if corrective_knowledge else "No additional knowledge found. Please analyze the error carefully."}

**Next Steps:**
1. Review the corrective knowledge above, especially required fields and validation rules
2. Identify what was missing or incorrect in the previous attempt
3. Retry the operation with complete and accurate information

Do not give up - use the knowledge above to correct the issue and retry."""
    )

    return {
        "messages": [correction_message],
        "correction_attempts": correction_attempts + 1,
        "last_error_context": error_context,
        "is_correction_mode": True,
    }
