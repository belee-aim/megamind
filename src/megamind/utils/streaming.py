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


async def stream_response_with_ping(
    graph, inputs, config, provider=None, zep_client=None, zep_thread_id=None
):
    """
    Streams responses from the graph with agent status visibility.

    Events:
    - agent_reasoning: Agent's internal reasoning/planning content
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

    # All known agent nodes in the graph
    KNOWN_AGENTS = {
        "knowledge_analyst",
        "report_analyst",
        "operations_specialist",
    }

    # Agents that use structured output - their streaming is "reasoning"
    STRUCTURED_OUTPUT_AGENTS = {
        "knowledge_analyst",
        "report_analyst",
        "operations_specialist",
    }

    async def stream_producer():
        try:
            current_agent = None

            async for event in graph.astream_events(inputs, config, version="v2"):
                event_type = event.get("event")
                event_name = event.get("name", "")
                event_data = event.get("data", {})
                metadata = event.get("metadata", {})

                # Get langgraph_node from metadata - this is the parent graph node
                # even when we're inside nested chains/agents
                langgraph_node = metadata.get("langgraph_node", "")

                # Determine effective agent for this event:
                # 1. If langgraph_node is a known agent, use it (most accurate)
                # 2. Otherwise fall back to the tracked current_agent
                effective_agent = current_agent
                if langgraph_node in KNOWN_AGENTS:
                    effective_agent = langgraph_node

                # Track current agent from node starts - only update for known agent nodes
                # This prevents internal chain names like "model" or "tools" from overwriting
                if event_type == "on_chain_start":
                    check_name = langgraph_node or event_name
                    if check_name in KNOWN_AGENTS:
                        current_agent = check_name
                        effective_agent = check_name

                # Detect tool calls
                if event_type == "on_tool_start":
                    tool_name = event_name
                    tool_input = event_data.get("input", {})

                    # Update current agent if this is a subagent delegation
                    if tool_name == "task" and isinstance(tool_input, dict):
                        subagent = tool_input.get("subagent_type", "")
                        if subagent:
                            current_agent = subagent

                    await queue.put(
                        {
                            "type": "agent_tool_call",
                            "agent": effective_agent,
                            "tool": tool_name,
                            "input_preview": str(tool_input)[:200],
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
                            # Normalize ERPNext variations to ERP
                            text_content = text_content.replace("ERPNext", "ERP")
                            text_content = text_content.replace("ERP Next", "ERP")
                            text_content = text_content.replace("ERPNEXT", "ERP")
                            text_content = text_content.replace("erpnext", "ERP")

                            # Determine event type based on agent
                            # Agents in STRUCTURED_OUTPUT_AGENTS produce reasoning
                            # Others (incl. orchestrator_response_node) produce user content
                            if effective_agent in STRUCTURED_OUTPUT_AGENTS:
                                await queue.put(
                                    {
                                        "type": "agent_reasoning",
                                        "agent": effective_agent,
                                        "content": text_content,
                                    }
                                )
                            else:
                                await queue.put(
                                    {
                                        "type": "stream_event",
                                        "agent": effective_agent,
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

                    if event_type == "agent_tool_call":
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
