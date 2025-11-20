"""
Knowledge capture node that extracts and saves valuable ERPNext knowledge from conversations.

This node runs after successful user interactions and automatically:
1. Analyzes the conversation for valuable knowledge
2. Extracts best practices, shortcuts, error solutions, and general knowledge
3. Saves to appropriate tables:
   - Best practices/shortcuts → process_definitions + erpnext_knowledge (dual save)
   - Error solutions/general → erpnext_knowledge only
"""

import asyncio
import hashlib
import json
from datetime import datetime

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.runnables import RunnableConfig
from loguru import logger
from pydantic import ValidationError

from megamind import prompts
from megamind.clients.titan_client import TitanClient
from megamind.configuration import Configuration
from megamind.graph.schemas import KnowledgeExtractionResult, KnowledgeEntrySchema
from megamind.graph.states import AgentState


async def knowledge_capture_node(state: AgentState, config: RunnableConfig):
    """
    Knowledge capture node - schedules background extraction and saving.

    This node returns immediately without blocking, scheduling the knowledge
    extraction as a background task.
    """
    logger.debug("Knowledge capture node invoked")

    # Schedule background task (fire-and-forget)
    # Create copies to avoid state mutation in background task
    asyncio.create_task(_extract_and_save_knowledge(state.copy(), config.copy()))
    logger.debug("Knowledge capture background task scheduled")

    # Return immediately
    return state


async def _extract_and_save_knowledge(state: AgentState, config: RunnableConfig):
    """
    Background task that extracts knowledge from conversation and saves to Titan.

    For best_practice/shortcut:
        1. Generate unique process_id
        2. Save to process_definitions table
        3. Save to erpnext_knowledge table with process_id reference

    For error_solution/general_knowledge:
        1. Save to erpnext_knowledge table only

    For response_optimization:
        1. Check if metrics exceed thresholds
        2. Save to erpnext_knowledge table with optimization metadata
    """
    try:
        # Extract conversation messages
        messages = state.get("messages", [])
        if not messages or len(messages) < 2:
            logger.debug("Insufficient messages for knowledge extraction")
            return

        # Extract performance metrics from state
        total_time_ms = state.get("total_response_time_ms", 0) or 0
        tool_call_count = state.get("tool_call_count", 0) or 0
        llm_latency_ms = state.get("llm_latency_ms", 0) or 0

        # Convert to seconds for threshold checks
        total_time_s = total_time_ms / 1000
        llm_latency_s = llm_latency_ms / 1000

        # Check if response was slow (exceeds any threshold)
        is_slow_response = (
            total_time_s > 30 or tool_call_count > 3 or llm_latency_s > 10
        )

        if is_slow_response:
            logger.info(
                f"Slow response detected: total_time={total_time_s:.1f}s, "
                f"tool_calls={tool_call_count}, llm_latency={llm_latency_s:.1f}s"
            )

        # Format conversation for LLM
        conversation_text = _format_conversation(
            messages, total_time_ms, tool_call_count, llm_latency_ms, is_slow_response
        )
        logger.debug(
            f"Conversation formatted: {len(messages)} messages -> {len(conversation_text)} chars"
        )

        logger.info("Analyzing conversation for knowledge extraction")
        logger.debug(
            f"Calling knowledge extraction LLM with {len(conversation_text)} chars"
        )

        # Call LLM to extract knowledge
        extraction_result = await _call_knowledge_extraction_llm(conversation_text)

        if not extraction_result.should_save:
            logger.info(
                f"No valuable knowledge detected: {len(messages)} messages analyzed, "
                f"{len(conversation_text)} chars processed"
            )
            return

        if not extraction_result.entries:
            logger.info("Knowledge extraction returned no entries")
            return

        logger.info(
            f"Extracted {len(extraction_result.entries)} knowledge entries to save"
        )

        # Log entry type distribution
        type_counts = {}
        for entry in extraction_result.entries:
            type_counts[entry.knowledge_type] = (
                type_counts.get(entry.knowledge_type, 0) + 1
            )
        logger.info(f"Entry type distribution: {type_counts}")

        # Save each knowledge entry
        titan_client = TitanClient()
        logger.debug("Initialized Titan client for knowledge save operations")

        failed_count = 0
        for idx, entry in enumerate(extraction_result.entries, 1):
            logger.debug(
                f"Processing entry {idx}/{len(extraction_result.entries)}: '{entry.title}'"
            )
            try:
                await _save_knowledge_entry(entry, titan_client)
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to save knowledge entry '{entry.title}': {e}")
                # Continue with next entry even if one fails

        successful_saves = len(extraction_result.entries) - failed_count
        logger.info(
            f"Knowledge capture completed: {len(extraction_result.entries)} extracted, "
            f"{successful_saves} saved successfully"
        )

    except Exception as e:
        logger.error(f"Error in knowledge capture background task: {e}")


def _format_conversation(
    messages,
    total_time_ms: float = 0,
    tool_call_count: int = 0,
    llm_latency_ms: float = 0,
    is_slow_response: bool = False,
) -> str:
    """
    Format conversation messages into readable text for LLM analysis.
    Includes MCP tool invocations for learning usage patterns.
    Includes performance metrics if response was slow.

    Args:
        messages: List of conversation messages
        total_time_ms: Total response time in milliseconds
        tool_call_count: Number of tool calls made
        llm_latency_ms: LLM latency in milliseconds
        is_slow_response: Whether response exceeded performance thresholds

    Returns:
        Formatted conversation string with tool calls and optional metrics
    """
    formatted = []

    # Add performance metrics header if response was slow
    if is_slow_response and (total_time_ms > 0 or tool_call_count > 0):
        total_time_s = total_time_ms / 1000
        llm_latency_s = llm_latency_ms / 1000

        formatted.append("=== PERFORMANCE METRICS ===")
        formatted.append(f"Total Response Time: {total_time_s:.1f}s (threshold: 30s)")
        formatted.append(f"Total Tool Calls: {tool_call_count} (threshold: 3)")
        formatted.append(f"LLM Latency: {llm_latency_s:.1f}s (threshold: 10s)")
        formatted.append(
            "⚠️  Response exceeded performance thresholds - analyze for optimization opportunities\n"
        )
        formatted.append("=========================\n")

    # Track knowledge search calls for analysis
    knowledge_search_count = 0

    for msg in messages:
        # Get message type and content
        msg_type = getattr(msg, "type", "unknown")
        content = getattr(msg, "content", "")

        # Skip empty or system messages
        if not content or msg_type == "system":
            continue

        # Format based on message type
        if msg_type == "human":
            formatted.append(f"User: {content}")

        elif msg_type == "ai":
            formatted.append(f"Assistant: {content}")

            # Extract tool calls from AIMessage for MCP tool usage analysis
            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls:
                for tool_call in tool_calls:
                    tool_name = tool_call.get("name", "unknown")
                    tool_args = tool_call.get("args", {})

                    # Format tool call with key arguments (exclude sensitive data)
                    args_summary = {
                        k: v
                        for k, v in tool_args.items()
                        if k != "user_token" and v is not None
                    }

                    # Format arguments for readability
                    args_str = ", ".join(
                        f"{k}={repr(v)[:50]}" for k, v in args_summary.items()
                    )

                    # Special highlighting for knowledge searches
                    if tool_name == "search_erpnext_knowledge":
                        knowledge_search_count += 1
                        formatted.append(
                            f"  🔍 Knowledge Search #{knowledge_search_count}: {tool_name}({args_str})"
                        )
                    else:
                        formatted.append(f"  → Tool Call: {tool_name}({args_str})")

        elif msg_type == "tool":
            # Include tool results but keep concise
            tool_name = getattr(msg, "name", "tool")
            # Truncate long results
            result_preview = content[:200] + "..." if len(content) > 200 else content

            # Special formatting for knowledge search results
            if tool_name == "search_erpnext_knowledge":
                # Try to extract result count from content
                result_count = "unknown"
                if "entries found" in content:
                    # Extract number from "Knowledge Search Results (X entries found)"
                    import re

                    match = re.search(r"\((\d+) entries? found\)", content)
                    if match:
                        result_count = match.group(1)

                formatted.append(
                    f"  📊 Knowledge Search Results: {result_count} entries returned"
                )
                formatted.append(f"     Preview: {result_preview}")
            else:
                formatted.append(f"Tool Result ({tool_name}): {result_preview}")

    return "\n\n".join(formatted)


def _parse_json_strings_to_dicts(data):
    """
    Recursively parse JSON strings to dictionaries.

    Some LLM models return nested JSON as strings instead of parsed dicts.
    This function recursively converts any JSON string fields to actual dicts/lists.

    Args:
        data: Data structure that may contain JSON strings

    Returns:
        Data structure with JSON strings converted to dicts/lists
    """
    if isinstance(data, str):
        # Try to parse as JSON
        try:
            parsed = json.loads(data)
            # Recursively parse the result in case it contains more JSON strings
            return _parse_json_strings_to_dicts(parsed)
        except (json.JSONDecodeError, TypeError):
            # Not valid JSON, return as-is
            return data
    elif isinstance(data, dict):
        # Recursively parse all dict values
        return {k: _parse_json_strings_to_dicts(v) for k, v in data.items()}
    elif isinstance(data, list):
        # Recursively parse all list items
        return [_parse_json_strings_to_dicts(item) for item in data]
    else:
        # Return primitives as-is
        return data


async def _call_knowledge_extraction_llm(
    conversation: str,
) -> KnowledgeExtractionResult:
    """
    Call LLM to extract knowledge from conversation.

    Handles cases where LLM returns JSON strings instead of parsed dicts
    by attempting to parse them manually.

    Args:
        conversation: Formatted conversation text

    Returns:
        KnowledgeExtractionResult with extracted entries
    """
    config = Configuration()
    llm = config.get_chat_model(custom_model="kimi-k2-thinking")

    # Format prompt with conversation
    prompt = prompts.knowledge_extraction_agent_instructions.format(
        conversation=conversation
    )

    # Use structured output
    structured_llm = llm.with_structured_output(KnowledgeExtractionResult)

    try:
        result: KnowledgeExtractionResult = await structured_llm.ainvoke(prompt)
        logger.debug(
            f"LLM extraction result: should_save={result.should_save}, entries={len(result.entries)}"
        )
        return result
    except ValidationError as e:
        # Check if error is about dict_type (JSON strings instead of dicts)
        error_str = str(e)
        if "dict_type" in error_str or "Input should be a valid dictionary" in error_str:
            logger.warning(
                "LLM returned JSON strings instead of dicts, attempting manual parsing..."
            )
            try:
                # Get raw response without structured output
                raw_response = await llm.ainvoke(prompt)
                raw_content = raw_response.content

                # Try to extract JSON from response
                # Look for JSON block in markdown code fence or raw JSON
                if "```json" in raw_content:
                    json_start = raw_content.find("```json") + 7
                    json_end = raw_content.find("```", json_start)
                    json_str = raw_content[json_start:json_end].strip()
                elif "```" in raw_content:
                    json_start = raw_content.find("```") + 3
                    json_end = raw_content.find("```", json_start)
                    json_str = raw_content[json_start:json_end].strip()
                else:
                    # Assume entire content is JSON
                    json_str = raw_content.strip()

                # Parse the JSON string
                parsed_json = json.loads(json_str)

                # Recursively convert any JSON strings to dicts
                parsed_data = _parse_json_strings_to_dicts(parsed_json)

                # Create KnowledgeExtractionResult from parsed data
                result = KnowledgeExtractionResult(**parsed_data)
                logger.info(
                    f"Successfully parsed JSON strings: should_save={result.should_save}, "
                    f"entries={len(result.entries)}"
                )
                return result

            except Exception as parse_error:
                logger.error(
                    f"Failed to manually parse JSON strings: {parse_error}", exc_info=True
                )
                # Fall through to return empty result

        # Log the original validation error
        logger.error(f"Validation error in knowledge extraction: {e}", exc_info=True)
        return KnowledgeExtractionResult(should_save=False, entries=[])

    except Exception as e:
        logger.error(f"Error calling knowledge extraction LLM: {e}", exc_info=True)
        # Return empty result on error
        return KnowledgeExtractionResult(should_save=False, entries=[])


async def _save_knowledge_entry(entry: KnowledgeEntrySchema, titan_client: TitanClient):
    """
    Save a knowledge entry to appropriate Titan tables.

    For best_practice/shortcut: saves to BOTH tables
    For response_optimization/error_solution/general_knowledge: saves to erpnext_knowledge only

    Args:
        entry: Knowledge entry to save
        titan_client: Titan API client
    """
    knowledge_type = entry.knowledge_type

    logger.info(
        f"Saving knowledge entry: type='{knowledge_type}', title='{entry.title}', "
        f"doctype='{entry.doctype_name or 'None'}', priority={entry.priority}"
    )

    # Check if this is a process (best_practice or shortcut)
    is_process = knowledge_type in ["best_practice", "shortcut"]

    if is_process:
        logger.debug(
            f"Entry '{entry.title}' type='{knowledge_type}' → dual save "
            f"(process_definitions + erpnext_knowledge)"
        )
    else:
        logger.debug(
            f"Entry '{entry.title}' type='{knowledge_type}' → erpnext_knowledge only"
        )

    if is_process:
        # Dual save: process_definitions + erpnext_knowledge
        await _save_as_process(entry, titan_client)
    else:
        # Single save: erpnext_knowledge only (includes response_optimization)
        await _save_as_knowledge(entry, titan_client)


async def _save_as_process(entry: KnowledgeEntrySchema, titan_client: TitanClient):
    """
    Save best practice or shortcut to BOTH process_definitions and erpnext_knowledge tables.

    Args:
        entry: Knowledge entry (must be best_practice or shortcut)
        titan_client: Titan API client
    """
    # Generate unique process_id
    process_id = _generate_process_id(
        entry.knowledge_type, entry.doctype_name, entry.title
    )
    logger.debug(f"Generated process_id: {process_id} for {entry.knowledge_type}")

    logger.info(f"Saving as process with ID: {process_id}")

    # 1. Save to process_definitions
    try:
        # Convert steps from dict of ProcessStepSchema to dict of dicts
        step_count = len(entry.steps) if entry.steps else 0
        logger.debug(
            f"Converting {step_count} process steps for process '{process_id}'"
        )

        steps_dict = {}
        if entry.steps:
            for step_num, step_schema in entry.steps.items():
                steps_dict[step_num] = {
                    "step_id": step_schema.step_id,
                    "title": step_schema.title,
                    "description": step_schema.description,
                    "action_type": step_schema.action_type,
                }
                if step_schema.target_doctype:
                    steps_dict[step_num]["target_doctype"] = step_schema.target_doctype
                if step_schema.mcp_tool_name:
                    steps_dict[step_num]["mcp_tool_name"] = step_schema.mcp_tool_name

        await titan_client.create_process_definition(
            process_id=process_id,
            name=entry.title,
            description=entry.summary,
            category=entry.category or "General",
            steps=steps_dict,
            trigger_conditions=entry.trigger_conditions,
            prerequisites=entry.prerequisites,
            version="1.0",
        )

        logger.info(f"Process definition saved successfully: {process_id}")

    except Exception as e:
        logger.error(f"Failed to save process definition: {e}")
        raise

    # 2. Save to erpnext_knowledge with process_id reference
    try:
        # Format content with queries and process reference
        formatted_content = _format_content_with_queries(
            content=entry.content,
            possible_queries=entry.possible_queries,
            process_id=process_id,
        )

        await titan_client.create_knowledge_entry(
            title=entry.title,
            content=formatted_content,
            summary=entry.summary,
            doctype_name=entry.doctype_name,
            module=entry.module,
            priority=entry.priority,
            meta_data={
                "process_id": process_id,
                "knowledge_type": entry.knowledge_type,
                "auto_captured": True,
                "captured_at": datetime.now().isoformat(),
            },
            version=1,
        )

        logger.info(
            f"Knowledge entry saved successfully with process reference: {process_id}"
        )

    except Exception as e:
        logger.error(f"Failed to save knowledge entry: {e}")
        raise


async def _save_as_knowledge(entry: KnowledgeEntrySchema, titan_client: TitanClient):
    """
    Save error solution, general knowledge, or response optimization to erpnext_knowledge table only.

    Args:
        entry: Knowledge entry
        titan_client: Titan API client
    """
    try:
        # Format content with queries (no process reference for non-process knowledge)
        formatted_content = _format_content_with_queries(
            content=entry.content,
            possible_queries=entry.possible_queries,
            process_id=None,
        )

        logger.debug(
            f"Knowledge metadata: module={entry.module or 'None'}, "
            f"queries={len(entry.possible_queries)}"
        )

        # Build metadata
        meta_data = {
            "knowledge_type": entry.knowledge_type,
            "auto_captured": True,
            "captured_at": datetime.now().isoformat(),
        }

        # Add optimization-specific metadata if this is a response_optimization entry
        if entry.knowledge_type == "response_optimization":
            if entry.original_metrics:
                meta_data["original_metrics"] = entry.original_metrics
            if entry.optimization_approach:
                meta_data["optimization_approach"] = entry.optimization_approach
            if entry.estimated_improvement:
                meta_data["estimated_improvement"] = entry.estimated_improvement

            # Add search query optimization metadata if present
            if entry.ineffective_search_query:
                meta_data["ineffective_search_query"] = entry.ineffective_search_query
            if entry.better_search_query:
                meta_data["better_search_query"] = entry.better_search_query
            if entry.search_query_improvements:
                meta_data["search_query_improvements"] = entry.search_query_improvements

            logger.debug(
                f"Response optimization metadata: "
                f"metrics={entry.original_metrics}, "
                f"improvement={entry.estimated_improvement}, "
                f"search_query_opt={bool(entry.ineffective_search_query)}"
            )

        await titan_client.create_knowledge_entry(
            title=entry.title,
            content=formatted_content,
            summary=entry.summary,
            doctype_name=entry.doctype_name,
            module=entry.module,
            priority=entry.priority,
            meta_data=meta_data,
            version=1,
        )

        logger.info(f"Knowledge entry saved successfully: {entry.title}")

    except Exception as e:
        logger.error(f"Failed to save knowledge entry: {e}")
        raise


def _generate_process_id(knowledge_type: str, doctype: str | None, title: str) -> str:
    """
    Generate unique process_id for process definitions.

    Format: proc_{prefix}_{doctype}_{hash}

    Args:
        knowledge_type: "best_practice" or "shortcut"
        doctype: Related DocType name (optional)
        title: Process title

    Returns:
        Unique process ID string

    Example:
        proc_bp_sales_order_a3f2e1
        proc_shortcut_payment_entry_7b4c9d
    """
    # Determine prefix
    prefix = "bp" if knowledge_type == "best_practice" else "shortcut"

    # Clean doctype name
    doctype_clean = (
        doctype.lower().replace(" ", "_").replace("-", "_") if doctype else "general"
    )

    # Generate hash from title + timestamp for uniqueness
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    hash_input = f"{title}{timestamp}"
    content_hash = hashlib.md5(hash_input.encode()).hexdigest()[:6]

    # Build process_id
    process_id = f"proc_{prefix}_{doctype_clean}_{content_hash}"

    return process_id


def _format_content_with_queries(
    content: str, possible_queries: list[str], process_id: str | None = None
) -> str:
    """
    Format content with queries at top for better similarity search.

    Structure:
    1. Queries section (for embedding matching)
    2. Separator
    3. Knowledge content
    4. Process reference (if applicable)

    Args:
        content: Original knowledge content
        possible_queries: List of possible search queries
        process_id: Optional process ID for cross-referencing

    Returns:
        Formatted content in markdown
    """
    parts = []

    # 1. Queries section (if queries exist)
    if possible_queries:
        parts.append("# Possible Queries\n")
        for query in possible_queries:
            parts.append(f"- {query}")
        parts.append("\n---\n")

    # 2. Knowledge content
    parts.append("# Knowledge\n")
    parts.append(content)

    # 3. Process reference (if applicable)
    if process_id:
        parts.append("\n\n---\n")
        parts.append(f"**Executable Process**: `{process_id}`\n\n")
        parts.append(
            f"This best practice is available as an executable process definition. "
            f"Refer to process `{process_id}` in the process_definitions table for "
            f"step-by-step execution details and automation capabilities."
        )

    return "\n".join(parts)
