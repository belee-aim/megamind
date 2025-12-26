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

    Uses tags from metadata for reliable subagent identification.
    Tags are set by SubAgentMiddleware when invoking subagents.

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

    # Known subagent types for tag-based identification
    # These names match the subagent "name" field in SubAgentMiddleware
    SUBAGENT_TYPES = {
        "knowledge",
        "report",
        "operations",
    }

    def get_agent_from_metadata(metadata: dict) -> str:
        """Extract subagent type from metadata tags.

        Tags are the most reliable way to identify subagents since they're
        explicitly set when invoking subagents via SubAgentMiddleware.
        Falls back to langgraph_node if no matching tag is found.

        Args:
            metadata: Event metadata containing tags and langgraph_node

        Returns:
            Subagent name if found in tags or langgraph_node, "orchestrator" otherwise
        """
        # Priority 1: Check tags (most reliable, explicitly set by middleware)
        tags = metadata.get("tags", [])
        for tag in tags:
            if tag in SUBAGENT_TYPES:
                return tag

        # Priority 2: Check langgraph_node (fallback for graph nodes)
        langgraph_node = metadata.get("langgraph_node", "")
        if langgraph_node in SUBAGENT_TYPES:
            return langgraph_node

        return "orchestrator"

    async def stream_producer():
        try:
            # Use messages + custom stream mode for subagent tool visibility
            # subgraphs=True enables real-time streaming from subagents
            async for chunk in graph.astream(
                inputs,
                config=config,
                stream_mode=["messages", "custom"],
                subgraphs=True,
            ):
                # With subgraphs=True, chunks come as:
                # (namespace_tuple, stream_mode, data)
                # where namespace_tuple identifies the subgraph path
                # e.g., () for root, ('task:abc123',) for subagent

                namespace = ()
                stream_mode = None
                data = None

                if isinstance(chunk, tuple):
                    if len(chunk) == 3:
                        # subgraphs=True format: (namespace, stream_mode, data)
                        namespace, stream_mode, data = chunk
                    elif len(chunk) == 2:
                        # Regular format: (stream_mode, data)
                        stream_mode, data = chunk
                    else:
                        continue
                else:
                    continue

                # Handle custom stream events (currently no special handling needed)
                if stream_mode == "custom":
                    continue

                if stream_mode == "messages":
                    message_chunk, metadata = (
                        data if isinstance(data, tuple) else (data, {})
                    )
                else:
                    # Not a recognized format
                    continue

                # Get agent from metadata tags
                effective_agent = get_agent_from_metadata(metadata)

                # Handle ToolMessage - tool results
                from langchain_core.messages import ToolMessage, AIMessage

                if isinstance(message_chunk, ToolMessage):
                    tool_name = getattr(message_chunk, "name", "")
                    tool_status = getattr(message_chunk, "status", "success")

                    # Show errors to help with debugging
                    if tool_status != "success":
                        content = (
                            message_chunk.content
                            if isinstance(message_chunk.content, str)
                            else str(message_chunk.content)
                        )
                        if content:
                            await queue.put(
                                {
                                    "type": "error",
                                    "message": content,
                                }
                            )
                    continue

                # Handle AIMessage chunks
                if not isinstance(message_chunk, AIMessage):
                    continue

                # Process content - stream text immediately
                if hasattr(message_chunk, "content") and message_chunk.content:
                    text_content = extract_text_content(message_chunk.content)
                    if text_content:
                        # Replace newlines and spaces with tokens
                        text_content = text_content.replace("\n", "|new_line|")
                        text_content = text_content.replace(" ", "|space|")
                        # Normalize ERPNext variations to ERP
                        text_content = text_content.replace("ERPNext", "ERP")
                        text_content = text_content.replace("ERP Next", "ERP")
                        text_content = text_content.replace("ERPNEXT", "ERP")
                        text_content = text_content.replace("erpnext", "ERP")

                        await queue.put(
                            {
                                "type": "stream_event",
                                "agent": effective_agent,
                                "content": text_content,
                            }
                        )

                # Handle tool calls from AIMessage
                if hasattr(message_chunk, "tool_calls") and message_chunk.tool_calls:
                    for tool_call in message_chunk.tool_calls:
                        tool_name = tool_call.get("name", "")
                        tool_args = tool_call.get("args", {})
                        await queue.put(
                            {
                                "type": "agent_tool_call",
                                "agent": effective_agent,
                                "tool": tool_name,
                                "input_preview": str(tool_args)[:200],
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
