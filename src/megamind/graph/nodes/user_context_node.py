"""
User context node - fetches user's personal knowledge before orchestration.
"""

from langchain_core.runnables import RunnableConfig
from loguru import logger

from megamind.graph.states import AgentState
from megamind.clients.zep_client import get_zep_client


async def user_context_node(state: AgentState, config: RunnableConfig):
    """
    Fetches user's personal knowledge from Zep before the orchestrator processes the request.

    This provides context about:
    - User's preferences and past interactions
    - User's role and responsibilities
    - Previous decisions and patterns
    """
    logger.debug("---USER CONTEXT NODE---")

    # Get user email from config
    cfg = config.get("configurable", {}) if config else {}
    user_email = cfg.get("user_email")

    if not user_email:
        logger.debug("No user email in config, skipping user context fetch")
        return {"user_context": None}

    # Get the user's query to search for relevant context
    messages = state.get("messages", [])
    if not messages:
        return {"user_context": None}

    # Get the last human message as the query
    last_message = messages[-1]
    query = getattr(last_message, "content", str(last_message))

    try:
        zep_client = get_zep_client()

        if not zep_client.is_available():
            logger.debug("Zep client not available, skipping user context")
            return {"user_context": None}

        # Search user's personal knowledge graph
        results = await zep_client.search_graph(
            query=query,
            user_id=user_email,
            limit=5,  # Keep it small for speed
        )

        if not results:
            logger.debug(f"No user context found for: {user_email}")
            return {"user_context": None}

        # Format results concisely
        context_parts = [f"# User Context for {user_email}"]
        for item in results:
            fact = item.get("fact", "")
            if fact:
                context_parts.append(f"- {fact}")

        user_context = "\n".join(context_parts)
        logger.debug(f"Fetched user context: {len(results)} facts")

        return {"user_context": user_context}

    except Exception as e:
        logger.error(f"Error fetching user context: {e}")
        return {"user_context": None}
