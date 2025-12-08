from langchain_core.runnables import RunnableConfig
from langchain_core.messages import AIMessage, SystemMessage
from loguru import logger
from pydantic import BaseModel, Field, AliasChoices
from typing import List

from megamind.configuration import Configuration
from megamind.graph.states import AgentState

PLANNER_PROMPT = """You are the Planner. Create a step-by-step execution plan.

## Available Specialists
| Specialist | Use For |
|------------|---------|
| semantic | Understanding processes, workflows, doctypes, schemas, workflow states/transitions |
| report | Generating and analyzing reports |
| system | CRUD operations, document search, system health |

## Rules
1. Break down the task into sequential steps
2. Assign each step to ONE specialist
3. Order steps logically (dependencies first)
4. Mark steps that can run in PARALLEL (no dependencies on each other)
5. Be specific about what each step should accomplish

Create a plan for the user's request."""


class PlanStep(BaseModel):
    """A single step in the execution plan."""

    step_number: int = Field(
        description="Step number (1-based)",
        validation_alias=AliasChoices("step_number", "id", "sequence"),
    )
    specialist: str = Field(description="Target specialist for this step")
    task: str = Field(
        description="Specific task description for the specialist",
        validation_alias=AliasChoices("task", "action", "description", "details"),
    )
    depends_on: List[int] = Field(
        default=[], description="Step numbers this depends on"
    )
    can_parallel: bool = Field(
        default=False,
        description="True if this step can run in parallel with other steps at same level",
        validation_alias=AliasChoices("can_parallel", "can_run_parallel", "parallel"),
    )


class ExecutionPlan(BaseModel):
    """Complete execution plan."""

    summary: str = Field(description="Brief summary of the plan")
    steps: List[PlanStep] = Field(description="List of execution steps")


def get_parallel_groups(steps: List[dict]) -> List[List[dict]]:
    """
    Group steps into execution batches.
    Steps in the same batch can run in parallel.
    """
    if not steps:
        return []

    groups = []
    current_group = []

    for step in steps:
        if step.get("can_parallel") and current_group:
            # Check if this step can join the current parallel group
            deps = set(step.get("depends_on", []))
            current_step_numbers = {s["step_number"] for s in current_group}

            # Can run in parallel if no dependency on current group
            if not deps.intersection(current_step_numbers):
                current_group.append(step)
                continue

        # Start new group
        if current_group:
            groups.append(current_group)
        current_group = [step]

    if current_group:
        groups.append(current_group)

    return groups


async def planner_node(state: AgentState, config: RunnableConfig):
    """
    Planner node. Creates an execution plan from complex requests.
    Supports parallel execution of independent steps.
    """
    logger.debug("---PLANNER---")

    configurable = Configuration.from_runnable_config(config)
    llm = configurable.get_chat_model()
    messages = state.get("messages", [])

    system_message = SystemMessage(content=PLANNER_PROMPT)

    # Use structured output for the plan
    structured_llm = llm.with_structured_output(ExecutionPlan)

    try:
        plan: ExecutionPlan = await structured_llm.ainvoke([system_message] + messages)

        logger.debug(f"Created plan with {len(plan.steps)} steps")

        # Convert to dict format for state
        plan_steps = [
            {
                "step_number": step.step_number,
                "specialist": step.specialist,
                "task": step.task,
                "depends_on": step.depends_on,
                "can_parallel": step.can_parallel,
            }
            for step in plan.steps
        ]

        # Group steps for parallel execution
        execution_groups = get_parallel_groups(plan_steps)

        # Get first group of specialists to run
        first_group = execution_groups[0] if execution_groups else []
        target_specialists = [step["specialist"] for step in first_group]

        return {
            "current_plan": plan_steps,
            "execution_groups": execution_groups,
            "current_group_index": 0,
            "plan_step_index": 0,
            "specialist_results": [],
            "pending_specialists": target_specialists,
            "next_action": "parallel"
            if len(target_specialists) > 1
            else ("route" if target_specialists else "respond"),
            "target_specialist": target_specialists[0]
            if len(target_specialists) == 1
            else None,
            "messages": [
                AIMessage(
                    content=f"I've created a plan: {plan.summary}\n\nExecuting {len(plan_steps)} steps..."
                )
            ],
        }

    except Exception as e:
        logger.error(f"Planner error: {e}")
        return {
            "next_action": "respond",
            "messages": [
                AIMessage(
                    content="I couldn't create a plan for this request. Could you provide more details?"
                )
            ],
        }
