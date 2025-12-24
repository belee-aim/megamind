"""Middleware for providing subagents to an agent via a `task` tool.

Adapted from deepagents/middleware/subagents.py for megamind's ERP use case.
"""

from collections.abc import Awaitable, Callable, Sequence
from typing import Any, NotRequired, TypedDict, cast

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware, InterruptOnConfig
from langgraph.errors import GraphInterrupt
from langchain.agents.middleware.types import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
)
from langchain.tools import BaseTool, ToolRuntime
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import StructuredTool
from langgraph.types import Command


class SubAgent(TypedDict):
    """Specification for a subagent.

    Define a subagent with its name, description, prompt, and tools.
    The SubAgentMiddleware will create the agent and expose it via the task tool.
    """

    name: str
    """The name of the agent (used as subagent_type in task tool)."""

    description: str
    """Description shown to orchestrator for routing decisions."""

    system_prompt: str
    """The system prompt for this subagent."""

    tools: Sequence[BaseTool | Callable | dict[str, Any]]
    """Tools available to this subagent."""

    model: NotRequired[str | BaseChatModel]
    """Optional model override. Defaults to `default_model`."""

    middleware: NotRequired[list[AgentMiddleware]]
    """Additional middleware to append after `default_middleware`."""

    interrupt_on: NotRequired[dict[str, bool | InterruptOnConfig]]
    """Tool configs for human-in-the-loop approval."""


class CompiledSubAgent(TypedDict):
    """A pre-compiled agent spec.

    Use this when you have an existing agent (created with create_agent)
    that you want to expose as a subagent.
    """

    name: str
    """The name of the agent."""

    description: str
    """Description shown to orchestrator for routing decisions."""

    runnable: Runnable
    """The compiled agent Runnable."""


# State keys that are excluded when passing state to subagents and when returning
# updates from subagents.
# When returning updates:
# 1. The messages key is handled explicitly to ensure only the final message is included
# 2. The todos and structured_response keys are excluded as they do not have a defined reducer
#    and no clear meaning for returning them from a subagent to the main agent.
_EXCLUDED_STATE_KEYS = {"messages", "todos", "structured_response"}

# ERP-specific task tool description
TASK_TOOL_DESCRIPTION = """Launch a specialist subagent to handle specific tasks.

Available specialists:
{available_agents}

## Usage Guidelines

1. **Parallel execution**: Launch multiple specialists concurrently when tasks are independent
2. **Results are internal**: Subagent results come back to you. Summarize them for the user.
3. **Stateless**: Each subagent invocation is isolated. Provide complete task context.
4. **Trust outputs**: Specialist outputs should generally be trusted.

## When to use the task tool:
- Complex multi-step operations (e.g., creating documents with validation)
- Domain-specific queries (knowledge lookup, report generation, CRUD operations)
- When you need focused expertise for a particular domain

## When NOT to use:
- Simple greetings or clarification questions
- Single, trivial tool calls
- When you already have the answer
"""

TASK_SYSTEM_PROMPT = """## Specialist Subagents

You have specialist subagents available via the `task` tool. Each specialist has specific expertise:

**Lifecycle:**
1. **Invoke** → Provide clear instructions and expected output format
2. **Execute** → Specialist completes the task autonomously  
3. **Return** → You receive the result (not visible to user)
4. **Respond** → Synthesize and present results to the user

**Parallelization**: When you have multiple independent queries, invoke specialists in parallel to save time.
"""


def _get_subagents(
    *,
    default_model: str | BaseChatModel,
    default_tools: Sequence[BaseTool | Callable | dict[str, Any]],
    default_middleware: list[AgentMiddleware] | None,
    default_interrupt_on: dict[str, bool | InterruptOnConfig] | None,
    subagents: list[SubAgent | CompiledSubAgent],
    general_purpose_agent: bool,
) -> tuple[dict[str, Any], list[str]]:
    """Create subagent instances from specifications.

    Returns:
        Tuple of (agent_dict, description_list) where agent_dict maps agent names
        to runnable instances and description_list contains formatted descriptions.
    """
    default_subagent_middleware = default_middleware or []

    agents: dict[str, Any] = {}
    subagent_descriptions = []

    # Create general-purpose agent if enabled
    if general_purpose_agent:
        general_purpose_middleware = [*default_subagent_middleware]
        if default_interrupt_on:
            general_purpose_middleware.append(
                HumanInTheLoopMiddleware(interrupt_on=default_interrupt_on)
            )
        general_purpose_subagent = create_agent(
            default_model,
            system_prompt="You are a general-purpose assistant with access to all available tools.",
            tools=default_tools,
            middleware=general_purpose_middleware,
        )
        agents["general-purpose"] = general_purpose_subagent
        subagent_descriptions.append(
            "- general-purpose: General assistant with access to all tools"
        )

    # Process custom subagents
    for agent_ in subagents:
        subagent_descriptions.append(f"- {agent_['name']}: {agent_['description']}")

        # Handle pre-compiled agents
        if "runnable" in agent_:
            custom_agent = cast("CompiledSubAgent", agent_)
            agents[custom_agent["name"]] = custom_agent["runnable"]
            continue

        # Build agent from spec
        _tools = agent_.get("tools", list(default_tools))
        subagent_model = agent_.get("model", default_model)
        _middleware = (
            [*default_subagent_middleware, *agent_["middleware"]]
            if "middleware" in agent_
            else [*default_subagent_middleware]
        )

        interrupt_on = agent_.get("interrupt_on", default_interrupt_on)
        if interrupt_on:
            _middleware.append(HumanInTheLoopMiddleware(interrupt_on=interrupt_on))

        agents[agent_["name"]] = create_agent(
            subagent_model,
            system_prompt=agent_["system_prompt"],
            tools=_tools,
            middleware=_middleware,
        )

    return agents, subagent_descriptions


def _create_task_tool(
    *,
    default_model: str | BaseChatModel,
    default_tools: Sequence[BaseTool | Callable | dict[str, Any]],
    default_middleware: list[AgentMiddleware] | None,
    default_interrupt_on: dict[str, bool | InterruptOnConfig] | None,
    subagents: list[SubAgent | CompiledSubAgent],
    general_purpose_agent: bool,
    task_description: str | None = None,
) -> BaseTool:
    """Create a task tool for invoking subagents.

    Returns:
        A StructuredTool that can invoke subagents by type.
    """
    subagent_graphs, subagent_descriptions = _get_subagents(
        default_model=default_model,
        default_tools=default_tools,
        default_middleware=default_middleware,
        default_interrupt_on=default_interrupt_on,
        subagents=subagents,
        general_purpose_agent=general_purpose_agent,
    )
    subagent_description_str = "\n".join(subagent_descriptions)

    def _return_command_with_state_update(result: dict, tool_call_id: str) -> Command:
        state_update = {
            k: v for k, v in result.items() if k not in _EXCLUDED_STATE_KEYS
        }
        # Strip trailing whitespace to prevent API errors with Anthropic
        message_text = (
            result["messages"][-1].text.rstrip() if result["messages"][-1].text else ""
        )
        return Command(
            update={
                **state_update,
                "messages": [ToolMessage(message_text, tool_call_id=tool_call_id)],
            }
        )

    def _validate_and_prepare_state(
        subagent_type: str, description: str, runtime: ToolRuntime
    ) -> tuple[Runnable, dict]:
        """Prepare state for invocation."""
        subagent = subagent_graphs[subagent_type]
        subagent_state = {
            k: v for k, v in runtime.state.items() if k not in _EXCLUDED_STATE_KEYS
        }
        subagent_state["messages"] = [HumanMessage(content=description)]
        return subagent, subagent_state

    # Build description
    if task_description is None:
        task_description = TASK_TOOL_DESCRIPTION.format(
            available_agents=subagent_description_str
        )
    elif "{available_agents}" in task_description:
        task_description = task_description.format(
            available_agents=subagent_description_str
        )

    def task(
        description: str,
        subagent_type: str,
        runtime: ToolRuntime,
    ) -> str | Command:
        """Invoke a specialist subagent with a task description."""
        if subagent_type not in subagent_graphs:
            allowed = ", ".join([f"`{k}`" for k in subagent_graphs])
            return f"Unknown subagent '{subagent_type}'. Available: {allowed}"

        subagent, state = _validate_and_prepare_state(
            subagent_type, description, runtime
        )

        try:
            result = subagent.invoke(state, runtime.config)
        except GraphInterrupt:
            # Re-raise GraphInterrupt so it propagates to pause the graph
            # This is critical for human-in-the-loop flows in nested subagents
            raise
        except Exception as e:
            # Return the error as a message so the orchestrator can see it
            # and potentially adjust the task or try a different approach
            error_msg = f"Subagent '{subagent_type}' encountered an error: {type(e).__name__}: {e}"
            return error_msg

        if not runtime.tool_call_id:
            raise ValueError("Tool call ID is required for subagent invocation")

        return _return_command_with_state_update(result, runtime.tool_call_id)

    async def atask(
        description: str,
        subagent_type: str,
        runtime: ToolRuntime,
    ) -> str | Command:
        """Async: Invoke a specialist subagent with a task description."""
        if subagent_type not in subagent_graphs:
            allowed = ", ".join([f"`{k}`" for k in subagent_graphs])
            return f"Unknown subagent '{subagent_type}'. Available: {allowed}"

        subagent, state = _validate_and_prepare_state(
            subagent_type, description, runtime
        )

        try:
            result = await subagent.ainvoke(state, config={"tags": [subagent_type]})
        except GraphInterrupt:
            # Re-raise GraphInterrupt so it propagates to pause the graph
            # This is critical for human-in-the-loop flows in nested subagents
            raise
        except Exception as e:
            # Return the error as a message so the orchestrator can see it
            # and potentially adjust the task or try a different approach
            error_msg = f"Subagent '{subagent_type}' encountered an error: {type(e).__name__}: {e}"
            return error_msg

        if not runtime.tool_call_id:
            raise ValueError("Tool call ID is required for subagent invocation")

        return _return_command_with_state_update(result, runtime.tool_call_id)

    return StructuredTool.from_function(
        name="task",
        func=task,
        coroutine=atask,
        description=task_description,
    )


class SubAgentMiddleware(AgentMiddleware):
    """Middleware that provides a `task` tool for invoking specialist subagents.

    This middleware enables the orchestrator to delegate work to specialized agents
    for knowledge queries, report generation, and CRUD operations.

    Example:
        ```python
        from megamind.graph.middleware.subagent_middleware import (
            SubAgentMiddleware,
            CompiledSubAgent,
        )

        # Using pre-compiled agents
        knowledge_agent = create_agent(llm, tools=knowledge_tools, ...)
        subagents = [
            CompiledSubAgent(
                name="knowledge",
                description="Business processes and documentation",
                runnable=knowledge_agent,
            ),
        ]

        orchestrator = create_agent(
            llm,
            middleware=[
                SubAgentMiddleware(
                    default_model=llm,
                    subagents=subagents,
                    general_purpose_agent=False,
                )
            ],
        )
        ```
    """

    def __init__(
        self,
        *,
        default_model: str | BaseChatModel,
        default_tools: Sequence[BaseTool | Callable | dict[str, Any]] | None = None,
        default_middleware: list[AgentMiddleware] | None = None,
        default_interrupt_on: dict[str, bool | InterruptOnConfig] | None = None,
        subagents: list[SubAgent | CompiledSubAgent] | None = None,
        system_prompt: str | None = TASK_SYSTEM_PROMPT,
        general_purpose_agent: bool = False,
        task_description: str | None = None,
    ) -> None:
        """Initialize SubAgentMiddleware.

        Args:
            default_model: Model for building SubAgent specs (not CompiledSubAgents).
            default_tools: Default tools for general-purpose agent.
            default_middleware: Middleware applied to all built subagents.
            default_interrupt_on: Default HITL config for built subagents.
            subagents: List of SubAgent or CompiledSubAgent specs.
            system_prompt: Added to orchestrator's system prompt. Set to None to disable.
            general_purpose_agent: Whether to include a general-purpose subagent.
            task_description: Custom task tool description (supports {available_agents}).
        """
        super().__init__()
        self.system_prompt = system_prompt
        task_tool = _create_task_tool(
            default_model=default_model,
            default_tools=default_tools or [],
            default_middleware=default_middleware,
            default_interrupt_on=default_interrupt_on,
            subagents=subagents or [],
            general_purpose_agent=general_purpose_agent,
            task_description=task_description,
        )
        self.tools = [task_tool]

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Add subagent instructions to system prompt."""
        if self.system_prompt is not None:
            system_prompt = (
                request.system_prompt + "\n\n" + self.system_prompt
                if request.system_prompt
                else self.system_prompt
            )
            return handler(request.override(system_prompt=system_prompt))
        return handler(request)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """Async: Add subagent instructions to system prompt."""
        if self.system_prompt is not None:
            system_prompt = (
                request.system_prompt + "\n\n" + self.system_prompt
                if request.system_prompt
                else self.system_prompt
            )
            return await handler(request.override(system_prompt=system_prompt))
        return await handler(request)
