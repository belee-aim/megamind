from langchain_core.runnables import RunnableConfig
from langchain_core.messages import AIMessage, SystemMessage
from loguru import logger
from pydantic import BaseModel, Field
from typing import Optional, Literal

from megamind.configuration import Configuration
from megamind.graph.states import AgentState

ORCHESTRATOR_PROMPT = """# Aimee - AI Assistant for {company}

You are Aimee, an intelligent orchestrator helping {user_name} ({user_email}) with their tasks.

## User Context
- **Name**: {user_name}
- **Email**: {user_email}
- **Roles**: {user_roles}
- **Company**: {company}
- **Current Time**: {current_datetime}

## Your Role
Analyze the user's request and route to the right specialist OR respond directly if the answer is obvious.

**Important**: The company has already configured their business processes in the knowledge graph. 
Route to the **knowledge** specialist to retrieve company-specific workflows and processes.

## Specialist Routing Guide

| Specialist | Route When User Wants To... | Examples |
|------------|----------------------------|----------|
| **knowledge** | Understand processes, schemas, workflows, company structure | "How does our sales order work?", "What fields does Invoice have?", "Who approves purchase orders?" |
| **report** | Get reports, analytics, financial data | "Show revenue this month", "Stock balance report", "Accounts receivable aging" |
| **operations** | Create, update, delete documents, perform workflow actions | "Create a sales order", "Submit this invoice", "Update customer address" |

## Decision Rules

1. **respond** → Answer directly when:
   - Simple greeting or thanks
   - Clarification needed (missing doctype, name, or key info)
   - Question can be answered from conversation context

2. **route** → Delegate when:
   - Request clearly maps to ONE specialist
   - Single action or query

3. **plan** → Create multi-step plan when:
   - Request needs MULTIPLE specialists
   - Complex operation (e.g., "Create invoice and apply payment")
   - User asks for end-to-end process execution

## Execution Context
{context}

Analyze the request and respond with your decision."""

SYNTHESIS_PROMPT = """Based on the specialist results collected, provide a unified response to the user.

## Specialist Results
{results}

Synthesize a helpful, complete response that addresses the user's original question."""


class OrchestratorDecision(BaseModel):
    """Structured output for orchestrator decisions."""

    reasoning: str = Field(description="Brief explanation of your decision")
    action: Literal["plan", "route", "respond"] = Field(
        description="plan=complex task, route=delegate to specialist, respond=answer directly"
    )
    target_specialist: Optional[Literal["knowledge", "report", "operations"]] = Field(
        default=None,
        description="Required if action=route. knowledge=understand, report=analytics, operations=CRUD/actions",
    )
    response: Optional[str] = Field(
        default=None,
        description="Your response if action=respond. Include any questions for missing info.",
    )


async def orchestrator_node(state: AgentState, config: RunnableConfig):
    """
    Orchestrator node using plain LLM with structured output.
    Routes to specialists and synthesizes results.

    Flow:
    1. If there are pending plan steps with specialist results, check if more steps needed
    2. If all plan steps done, synthesize and respond
    3. Otherwise, analyze user request and decide action
    """
    logger.debug("---ORCHESTRATOR---")

    configurable = Configuration.from_runnable_config(config)
    llm = configurable.get_chat_model()
    messages = state.get("messages", [])
    specialist_results = state.get("specialist_results", [])
    current_plan = state.get("current_plan")
    execution_groups = state.get("execution_groups", [])
    current_group_index = state.get("current_group_index", 0)

    # Check if we're in plan execution mode with results to process
    if current_plan and specialist_results:
        # Check if there are more groups to execute
        if execution_groups and current_group_index < len(execution_groups) - 1:
            # More groups remaining - advance to next group
            next_group_index = current_group_index + 1
            next_group = execution_groups[next_group_index]
            target_specialists = [step["specialist"] for step in next_group]

            logger.debug(
                f"Advancing to group {next_group_index + 1}: {target_specialists}"
            )

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

        results_text = "\n\n".join(
            [
                f"**Result {i + 1}:**\n{result}"
                for i, result in enumerate(specialist_results)
            ]
        )

        synthesis_message = SystemMessage(
            content=SYNTHESIS_PROMPT.format(results=results_text)
        )
        response = await llm.ainvoke([synthesis_message] + messages)

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

    # Normal orchestration - decide what to do
    context_parts = []
    if current_plan:
        step_idx = state.get("plan_step_index", 0)
        context_parts.append(f"Executing plan step {step_idx + 1}/{len(current_plan)}")
        if specialist_results:
            context_parts.append(
                f"Previous results: {len(specialist_results)} collected"
            )

    execution_context = (
        "\n".join(context_parts) if context_parts else "New conversation"
    )

    # Extract user context from RunnableConfig
    cfg = config.get("configurable", {}) if config else {}
    company = cfg.get("company", "N/A")
    user_name = cfg.get("user_name", "User")
    user_email = cfg.get("user_email", "N/A")
    user_roles = cfg.get("user_roles", [])
    current_datetime = cfg.get("current_datetime", "N/A")

    # Format roles as comma-separated string
    roles_str = ", ".join(user_roles) if user_roles else "N/A"

    # Create prompt with user context
    system_message = SystemMessage(
        content=ORCHESTRATOR_PROMPT.format(
            company=company,
            user_name=user_name,
            user_email=user_email,
            user_roles=roles_str,
            current_datetime=current_datetime,
            context=execution_context,
        )
    )

    # Use structured output
    structured_llm = llm.with_structured_output(OrchestratorDecision)

    try:
        decision: OrchestratorDecision = await structured_llm.ainvoke(
            [system_message] + messages
        )

        logger.debug(
            f"Orchestrator decision: {decision.action} -> {decision.target_specialist}"
        )

        # Build response
        result = {
            "next_action": decision.action,
            "target_specialist": decision.target_specialist,
        }

        # If responding directly, add the message
        if decision.action == "respond" and decision.response:
            result["messages"] = [AIMessage(content=decision.response)]

        return result

    except Exception as e:
        logger.error(f"Orchestrator error: {e}")
        # Fallback to direct response
        return {
            "next_action": "respond",
            "messages": [
                AIMessage(
                    content="I encountered an issue processing your request. Could you please rephrase?"
                )
            ],
        }
