import httpx
from loguru import logger
from langchain_core.messages import AIMessage

from megamind.graph.states import AgentState

EXTERNAL_API_URL = "https://your-external-api.com/reconciliation"  # Replace with your actual API endpoint


async def bank_reconciliation_model_node(state: AgentState, config):
    """
    This node calls an external API to perform bank reconciliation calculations.
    """
    logger.debug("---BANK RECONCILIATION MODEL NODE---")

    messages = state.get("messages", [])
    if not messages:
        return state

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(EXTERNAL_API_URL, json={"messages": [msg.dict() for msg in messages]})
            response.raise_for_status()  # Raise an exception for bad status codes
            api_response = response.json()

            # Assuming the API returns a message in a "content" field
            new_message = AIMessage(content=api_response.get("content", "No content from API"))
            return {"messages": messages + [new_message]}

        except httpx.RequestError as e:
            logger.error(f"API request failed: {e}")
            error_message = AIMessage(content=f"Error calling reconciliation API: {e}")
            return {"messages": messages + [error_message]}
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            error_message = AIMessage(content=f"An unexpected error occurred during reconciliation: {e}")
            return {"messages": messages + [error_message]}