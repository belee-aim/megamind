from langchain_core.runnables import RunnableConfig
from langchain_core.messages import AIMessage, SystemMessage
from loguru import logger
from pydantic import BaseModel, Field
from typing import Optional, Literal

from megamind.configuration import Configuration
from megamind.graph.states import AgentState

ORCHESTRATOR_PROMPT = """# Aimee - AI Multi-Agent Orchestrator

You are Aimee, an intelligent orchestrator that coordinates a team of specialists.

## Your Role
Analyze the user's request and decide the best course of action.

## 5W3H1R Protocol
Before deciding, consider:
- **Who**: User/Stakeholder  | **When**: Timeframe/Deadline
- **Where**: Context/Location | **Why**: Purpose/Goal  
- **What**: Object/DocType   | **How**: Method/Process
- **How much**: Quantity     | **How long**: Duration
- **Result**: Expected Outcome

## Available Specialists
| Specialist | Use For |
|------------|---------|
| business_process | Understanding processes, doctypes, schemas |
| workflow | Workflow states, transitions, approvals |
| report | Generating and analyzing reports |
| system | CRUD operations, document search, system health |
| transaction | Bank reconciliation, stock entries |

## Decision Rules
1. **respond**: Simple greetings, clarifications, or if info is missing
2. **plan**: Complex multi-step tasks needing coordination
3. **route**: Single-specialist tasks you can delegate directly

## Current Context
{context}

Analyze and decide what to do next."""


class OrchestratorDecision(BaseModel):
    """Structured output for orchestrator decisions."""

    reasoning: str = Field(description="Brief explanation of your decision")
    action: Literal["plan", "route", "respond"] = Field(
        description="plan=complex task, route=delegate to specialist, respond=answer directly"
    )
    target_specialist: Optional[
        Literal["business_process", "workflow", "report", "system", "transaction"]
    ] = Field(default=None, description="Required if action=route")
    response: Optional[str] = Field(
        default=None,
        description="Your response if action=respond. Include any questions for missing info.",
    )


async def orchestrator_node(state: AgentState, config: RunnableConfig):
    """
    Orchestrator node using plain LLM with structured output.
    Routes to other nodes via state updates.
    """
    logger.debug("---ORCHESTRATOR---")

    configurable = Configuration.from_runnable_config(config)
    llm = configurable.get_chat_model()
    messages = state.get("messages", [])

    # Build context from state
    context_parts = []
    if state.get("current_plan"):
        plan = state["current_plan"]
        step_idx = state.get("plan_step_index", 0)
        context_parts.append(f"Executing plan step {step_idx + 1}/{len(plan)}")
        if state.get("specialist_results"):
            context_parts.append(
                f"Previous results: {len(state['specialist_results'])} collected"
            )

    context = "\n".join(context_parts) if context_parts else "New conversation"

    # Create prompt with context
    system_message = SystemMessage(content=ORCHESTRATOR_PROMPT.format(context=context))

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
