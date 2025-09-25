import asyncio
from fastapi.responses import StreamingResponse
from loguru import logger
from langchain_core.messages import AIMessage
import json


async def stream_response_with_ping(graph, inputs, config):
    """
    Streams responses from the graph with a ping mechanism to keep the connection alive.
    """
    queue = asyncio.Queue()

    async def stream_producer():
        try:
            async for chunk, _ in graph.astream(inputs, config, stream_mode="messages"):
                if isinstance(chunk, AIMessage) and chunk.content:
                    await queue.put(chunk.content)
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
