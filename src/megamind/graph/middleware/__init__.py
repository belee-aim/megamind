# Middleware package for megamind graph agents
from megamind.graph.middleware.subagent_middleware import (
    SubAgentMiddleware,
    SubAgent,
    CompiledSubAgent,
    TASK_SYSTEM_PROMPT,
    TASK_TOOL_DESCRIPTION,
)

__all__ = [
    "SubAgentMiddleware",
    "SubAgent",
    "CompiledSubAgent",
    "TASK_SYSTEM_PROMPT",
    "TASK_TOOL_DESCRIPTION",
]
