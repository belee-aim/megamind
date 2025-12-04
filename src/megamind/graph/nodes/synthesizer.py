from langchain_core.runnables import RunnableConfig
from langchain_core.messages import SystemMessage
from loguru import logger

from megamind.configuration import Configuration
from megamind.graph.states import AgentState


SYNTHESIZER_PROMPT = """You are the Synthesizer. Combine specialist results into a coherent response.

## Your Task
1. Review all specialist results
2. Combine them into a clear, unified response
3. Ensure the response directly addresses the user's original question
4. Format nicely with relevant details

Synthesize a helpful, complete response."""


async def synthesizer_node(state: AgentState, config: RunnableConfig):
    """
    Synthesizer node. Combines results from specialist executions.
    Supports parallel execution by tracking pending specialists.
    """
    logger.debug("---SYNTHESIZER---")

    configurable = Configuration.from_runnable_config(config)
    llm = configurable.get_chat_model()
    messages = state.get("messages", [])
    specialist_results = state.get("specialist_results", [])
    execution_groups = state.get("execution_groups", [])
    current_group_index = state.get("current_group_index", 0)

    # Check if there are more groups to execute
    if execution_groups and current_group_index < len(execution_groups) - 1:
        # More groups remaining - advance to next group
        next_group_index = current_group_index + 1
        next_group = execution_groups[next_group_index]
        target_specialists = [step["specialist"] for step in next_group]

        logger.debug(f"Advancing to group {next_group_index + 1}: {target_specialists}")

        return {
            "current_group_index": next_group_index,
            "pending_specialists": target_specialists,
            "next_action": "parallel" if len(target_specialists) > 1 else "route",
            "target_specialist": target_specialists[0]
            if len(target_specialists) == 1
            else None,
        }

    # All groups complete - synthesize final response
    logger.debug("All groups complete, synthesizing final response")

    # Build synthesis prompt with results
    results_text = (
        "\n\n".join(
            [
                f"**Result {i + 1}:**\n{result}"
                for i, result in enumerate(specialist_results)
            ]
        )
        if specialist_results
        else "No specialist results collected."
    )

    synthesis_prompt = f"""{SYNTHESIZER_PROMPT}

## Specialist Results
{results_text}

Provide a unified response to the user."""

    system_message = SystemMessage(content=synthesis_prompt)

    response = await llm.ainvoke([system_message] + messages)

    # Clear plan state after completion
    return {
        "messages": [response],
        "next_action": "respond",
        "current_plan": None,
        "execution_groups": None,
        "current_group_index": None,
        "plan_step_index": None,
        "specialist_results": None,
        "pending_specialists": None,
    }
