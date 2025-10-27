import asyncio
import json
from langchain_core.runnables import RunnableConfig
from loguru import logger

from megamind import prompts
from megamind.clients.supa_client import get_supabase_client
from megamind.configuration import Configuration
from megamind.graph.schemas import ConversationSummary

from ..states import AgentState


async def _summarize_and_save(state: AgentState, config: RunnableConfig):
    """
    The core logic for summarizing and saving the conversation, to be run in the background.
    """
    logger.debug("---BACKGROUND CONTENT AGENT---")
    configurable = Configuration.from_runnable_config(config)
    supabase_client = get_supabase_client()

    # Get the full conversation history
    messages = state.get("messages", [])
    conversation_text = "\n".join([f"{m.type}: {m.content}" for m in messages])

    # Use an LLM to generate the summary
    llm = configurable.get_chat_model()
    prompt = prompts.content_agent_instructions.format(
        conversation=conversation_text
    )

    try:
        response = await llm.ainvoke(prompt)
        try:
            # Remove markdown formatting if present
            content = response.content
            if content.startswith("```json"):
                content = content[7:-4]
            data = json.loads(content)
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON from LLM response: {response.content}")
            data = {}
        summary_result = ConversationSummary(
            general_content=data.get("general_content", ""),
            key_points=data.get("key_points", []),
            structured_data=data.get("structured_data", {}),
        )

        # Save the summary to the database
        session_id = config["configurable"]["thread_id"]
        supabase_client.table("chat_contexts").upsert(
            {
                "session_id": session_id,
                "general_content": summary_result.general_content,
                "key_points": summary_result.key_points,
                "structured_data": summary_result.structured_data,
            },
            on_conflict="session_id",
        ).execute()
        logger.info(f"Successfully saved conversation summary for session {session_id}")
    except Exception as e:
        session_id = config.get("configurable", {}).get("thread_id", "unknown")
        logger.error(f"Failed to save conversation summary for session {session_id}: {e}")


async def content_agent_node(state: AgentState, config: RunnableConfig):
    """
    Processes the conversation history asynchronously by creating a background task.
    """
    logger.debug("---CONTENT AGENT NODE (scheduling background task)---")
    asyncio.create_task(_summarize_and_save(state.copy(), config.copy()))