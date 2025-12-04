import asyncio
from fastapi.responses import StreamingResponse
from loguru import logger
from langchain_core.messages import AIMessage, ToolMessage
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
    "orchestrator_node": "Orchestrator",
    "planner_node": "Planner",
    "synthesizer_node": "Synthesizer",
    "business_process_analyst": "Business Process Analyst",
    "workflow_analyst": "Workflow Analyst",
    "report_analyst": "Report Analyst",
    "system_specialist": "System Specialist",
    "transaction_specialist": "Transaction Specialist",
}


async def stream_response_with_ping(graph, inputs, config, provider=None):
    """
    Streams responses from the graph with agent status visibility.

    Events:
    - agent_start: When an agent begins processing
    - agent_thinking: Agent's reasoning/decision (from structured output)
    - agent_tool_call: When agent calls a tool
    - stream_event: Text content being streamed
    - done: Stream complete

    All newline characters are replaced with |new_line| token for consistent formatting.

    Args:
        graph: LangGraph graph to stream from
        inputs: Input data for the graph
        config: Configuration for the graph
        provider: Optional provider name (reserved for future provider-specific processing)
    """
    queue = asyncio.Queue()

    async def stream_producer():
        try:
            current_agent = None

            # Use 'updates' stream mode to see node-level updates
            async for event in graph.astream_events(inputs, config, version="v2"):
                event_type = event.get("event")
                event_name = event.get("name", "")
                event_data = event.get("data", {})

                # Detect node/agent starts
                if event_type == "on_chain_start":
                    if event_name in AGENT_DISPLAY_NAMES:
                        current_agent = event_name
                        display_name = AGENT_DISPLAY_NAMES.get(event_name, event_name)
                        await queue.put(
                            {
                                "type": "agent_start",
                                "agent": event_name,
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

                # Detect tool calls
                if event_type == "on_tool_start":
                    tool_name = event_name
                    tool_input = event_data.get("input", {})
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
                            await queue.put(
                                {
                                    "type": "stream_event",
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

                    elif event_type == "stream_event":
                        # Send content stream
                        content = item.get("content", "")
                        yield f"event: stream_event\ndata: {content}\n\n".encode(
                            "utf-8"
                        )

                    elif event_type == "error":
                        data = json.dumps(
                            {"message": item.get("message", "Unknown error")}
                        )
                        yield f"event: error\ndata: {data}\n\n".encode("utf-8")
                else:
                    # Legacy string content
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
