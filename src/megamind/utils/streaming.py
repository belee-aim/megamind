import asyncio
from fastapi.responses import StreamingResponse
from loguru import logger
from langchain_core.messages import AIMessage
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


async def stream_response_with_ping(graph, inputs, config, provider=None):
    """
    Streams responses from the graph with a ping mechanism to keep the connection alive.

    All newline characters are replaced with |new_line| token for consistent formatting.
    Empty chunks are also converted to |new_line| tokens to preserve formatting.

    Args:
        graph: LangGraph graph to stream from
        inputs: Input data for the graph
        config: Configuration for the graph
        provider: Optional provider name (reserved for future provider-specific processing)
    """
    queue = asyncio.Queue()

    async def stream_producer():
        try:
            async for chunk, _ in graph.astream(inputs, config, stream_mode="messages"):
                if isinstance(chunk, AIMessage) and chunk.content:
                    # Extract text content, handling different provider formats
                    text_content = extract_text_content(chunk.content)
                    if text_content:
                        # Replace newlines with |new_line| token for all providers
                        text_content = text_content.replace("\n", "|new_line|")

                        # Replace space with |space| token for all providers
                        text_content = text_content.replace(" ", "|space|")
                        await queue.put(text_content)
                    else:
                        # Empty chunks become |new_line| token
                        await queue.put("|new_line|")
        except Exception as e:
            logger.error(f"Error in stream producer: {e}")
            await queue.put(f"Error: {e}")
        finally:
            await queue.put(None)  # Signal completion

    async def response_generator():
        producer_task = asyncio.create_task(stream_producer())
        while True:
            try:
                chunk = await asyncio.wait_for(queue.get(), timeout=2.0)
                if chunk is None:
                    yield "event: done\ndata: {}\n\n".encode("utf-8")
                    break
                event_str = "event: stream_event\n"
                for line in str(chunk).splitlines():
                    data_str = f"data: {line}\n"
                    yield (event_str + data_str).encode("utf-8")
                yield b"\n"
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
