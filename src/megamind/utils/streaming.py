import asyncio
from fastapi.responses import StreamingResponse
from loguru import logger
import json


def extract_text_content(content):
    """
    Extract text from content, handling multiple provider formats.

    Different LLM providers return content in different formats:
    - Gemini: Returns plain string
    - Claude: Returns list of content blocks with 'type' and 'text' fields

    Args:
        content: Content from AIMessage, can be str or list

    Returns:
        str: Extracted text content
    """
    if isinstance(content, str):
        # Gemini format: plain string
        return content

    elif isinstance(content, list):
        # Claude format: list of content blocks
        text_parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
        return "".join(text_parts)

    # Fallback for unknown formats
    return str(content)


# Agent display names for user-friendly output
AGENT_DISPLAY_NAMES = {
    # Deep Agent orchestrator
    "deep_agent": "Orchestrator",
    # Legacy node names (kept for backwards compatibility during migration)
    "orchestrator_node": "Orchestrator",
    "planner_node": "Planner",
    "synthesizer_node": "Synthesizer",
    # Subagent names (Deep Agents format)
    "knowledge-analyst": "Knowledge Analyst",
    "knowledge_analyst": "Knowledge Analyst",
    "report-analyst": "Report Analyst",
    "report_analyst": "Report Analyst",
    "system-specialist": "System Specialist",
    "system_specialist": "System Specialist",
    "transaction-specialist": "Transaction Specialist",
    "transaction_specialist": "Transaction Specialist",
    "document-specialist": "Document Specialist",
    "document_specialist": "Document Specialist",
}


async def stream_response_with_ping(
    graph, inputs, config, provider=None, zep_client=None, zep_thread_id=None
):
    """
    Streams responses from the graph with agent status visibility.

    Events:
    - agent_start: When an agent begins processing
    - agent_reasoning: Agent's internal reasoning/planning (from structured output agents)
    - agent_thinking: Agent's final decision summary (from structured output)
    - agent_tool_call: When agent calls a tool
    - stream_event: Actual user-facing response content
    - done: Stream complete

    All newline characters are replaced with |new_line| token for consistent formatting.

    Args:
        graph: LangGraph graph to stream from
        inputs: Input data for the graph
        config: Configuration for the graph
        provider: Optional provider name (reserved for future provider-specific processing)
        zep_client: Optional ZepClient for syncing AI response to Zep thread
        zep_thread_id: Thread ID for Zep message sync
    """
    queue = asyncio.Queue()

    # Collect AI response content for Zep sync
    ai_response_content = []

    # Agents that use structured output - their streaming is "reasoning"
    # Synthesizer is NOT included because it produces actual user-facing responses
    # Note: Deep Agent does planning but also produces user-facing responses,
    # so we DON'T include it here to ensure responses stream to user
    STRUCTURED_OUTPUT_AGENTS = {
        "orchestrator_node",
        "planner_node",
    }

    async def stream_producer():
        try:
            current_agent = None

            # Use 'updates' stream mode to see node-level updates
            async for event in graph.astream_events(inputs, config, version="v2"):
                event_type = event.get("event")
                event_name = event.get("name", "")
                event_data = event.get("data", {})
                metadata = event.get("metadata", {})

                # Try to get langgraph_node from metadata for more accurate agent tracking
                langgraph_node = metadata.get("langgraph_node", "")

                # Detect node/agent starts
                if event_type == "on_chain_start":
                    # Check if this is a known agent node
                    check_name = langgraph_node or event_name
                    if check_name in AGENT_DISPLAY_NAMES:
                        current_agent = check_name
                        display_name = AGENT_DISPLAY_NAMES.get(check_name, check_name)
                        await queue.put(
                            {
                                "type": "agent_start",
                                "agent": check_name,
                                "display_name": display_name,
                            }
                        )

                # Detect agent decisions/reasoning (from structured output)
                if event_type == "on_chain_end" and current_agent:
                    output = event_data.get("output", {})

                    # Check for orchestrator decision
                    if isinstance(output, dict):
                        if "next_action" in output:
                            reasoning = output.get("reasoning", "")
                            action = output.get("next_action", "")
                            target = output.get("target_specialist", "")

                            if reasoning or action:
                                await queue.put(
                                    {
                                        "type": "agent_thinking",
                                        "agent": current_agent,
                                        "reasoning": reasoning,
                                        "action": action,
                                        "target": target,
                                    }
                                )

                # Detect tool calls - especially 'task' for subagent delegation
                if event_type == "on_tool_start":
                    tool_name = event_name
                    tool_input = event_data.get("input", {})

                    # If this is a 'task' tool, it's a subagent delegation
                    # Extract the subagent name from subagent_type field
                    if tool_name == "task" and isinstance(tool_input, dict):
                        subagent = tool_input.get("subagent_type", "")
                        if subagent and subagent in AGENT_DISPLAY_NAMES:
                            current_agent = subagent
                            display_name = AGENT_DISPLAY_NAMES.get(subagent, subagent)
                            await queue.put(
                                {
                                    "type": "agent_start",
                                    "agent": subagent,
                                    "display_name": display_name,
                                }
                            )

                    await queue.put(
                        {
                            "type": "agent_tool_call",
                            "agent": current_agent,
                            "tool": tool_name,
                            "input_preview": str(tool_input)[
                                :200
                            ],  # Truncate for display
                        }
                    )

                # Stream AI message content
                if event_type == "on_chat_model_stream":
                    chunk = event_data.get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        text_content = extract_text_content(chunk.content)
                        if text_content:
                            # Replace newlines and spaces with tokens
                            text_content = text_content.replace("\n", "|new_line|")
                            text_content = text_content.replace(" ", "|space|")

                            # Determine event type based on current agent
                            if current_agent in STRUCTURED_OUTPUT_AGENTS:
                                # This is reasoning/planning content
                                await queue.put(
                                    {
                                        "type": "agent_reasoning",
                                        "agent": current_agent,
                                        "content": text_content,
                                    }
                                )
                            else:
                                # This is actual user-facing response
                                # Include agent info so clients know which agent is responding
                                await queue.put(
                                    {
                                        "type": "stream_event",
                                        "agent": current_agent,
                                        "content": text_content,
                                    }
                                )

        except Exception as e:
            logger.error(f"Error in stream producer: {e}")
            await queue.put({"type": "error", "message": str(e)})
        finally:
            await queue.put(None)  # Signal completion

    async def response_generator():
        producer_task = asyncio.create_task(stream_producer())
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=2.0)
                if item is None:
                    # Sync AI response to Zep before sending done event
                    if zep_client and zep_thread_id and ai_response_content:
                        full_response = "".join(ai_response_content)
                        # Decode tokens back to readable text
                        full_response = full_response.replace("|new_line|", "\n")
                        full_response = full_response.replace("|space|", " ")
                        try:
                            await zep_client.add_message(
                                thread_id=zep_thread_id,
                                role="assistant",
                                content=full_response,
                            )
                            logger.debug(
                                f"Synced AI response to Zep thread: {zep_thread_id}"
                            )
                        except Exception as e:
                            logger.warning(f"Failed to sync AI response to Zep: {e}")

                    yield "event: done\ndata: {}\n\n".encode("utf-8")
                    break

                if isinstance(item, dict):
                    event_type = item.get("type", "stream_event")

                    if event_type == "agent_start":
                        # Send agent start event
                        data = json.dumps(
                            {
                                "agent": item.get("agent"),
                                "display_name": item.get("display_name"),
                            }
                        )
                        yield f"event: agent_start\ndata: {data}\n\n".encode("utf-8")

                    elif event_type == "agent_thinking":
                        # Send thinking/reasoning event
                        data = json.dumps(
                            {
                                "agent": item.get("agent"),
                                "reasoning": item.get("reasoning", ""),
                                "action": item.get("action", ""),
                                "target": item.get("target", ""),
                            }
                        )
                        yield f"event: agent_thinking\ndata: {data}\n\n".encode("utf-8")

                    elif event_type == "agent_tool_call":
                        # Send tool call event
                        data = json.dumps(
                            {
                                "agent": item.get("agent"),
                                "tool": item.get("tool"),
                                "input_preview": item.get("input_preview", ""),
                            }
                        )
                        yield f"event: agent_tool_call\ndata: {data}\n\n".encode(
                            "utf-8"
                        )

                    elif event_type == "agent_reasoning":
                        # Send reasoning stream (from orchestrator/planner)
                        data = json.dumps(
                            {
                                "agent": item.get("agent"),
                                "content": item.get("content", ""),
                            }
                        )
                        yield f"event: agent_reasoning\ndata: {data}\n\n".encode(
                            "utf-8"
                        )

                    elif event_type == "stream_event":
                        # Send actual response content stream with agent info
                        content = item.get("content", "")
                        agent = item.get("agent")
                        # Collect for Zep sync
                        ai_response_content.append(content)
                        data = json.dumps({"agent": agent, "content": content})
                        yield f"event: stream_event\ndata: {data}\n\n".encode("utf-8")

                    elif event_type == "error":
                        data = json.dumps(
                            {"message": item.get("message", "Unknown error")}
                        )
                        yield f"event: error\ndata: {data}\n\n".encode("utf-8")
                else:
                    # Legacy string content
                    ai_response_content.append(str(item))
                    yield f"event: stream_event\ndata: {item}\n\n".encode("utf-8")

            except asyncio.TimeoutError:
                yield "event: ping\ndata: {}\n\n".encode("utf-8")
            except Exception as e:
                logger.error(f"Error in response generator: {e}")
                error_data = {"message": "An error occurred during the stream."}
                yield f"event: error\ndata: {json.dumps(error_data)}\n\n".encode(
                    "utf-8"
                )
                break
        await producer_task

    return StreamingResponse(response_generator(), media_type="text/event-stream")
