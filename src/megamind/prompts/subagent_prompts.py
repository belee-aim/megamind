"""
System prompts for Megamind subagents.

NOTE: These prompts are deprecated. Use prompts from deep_agent_prompts.py instead.
This file is kept for backwards compatibility during migration.
"""

# Re-export from new location for backwards compatibility
from megamind.prompts.deep_agent_prompts import (
    BUSINESS_PROCESS_ANALYST_PROMPT,
    WORKFLOW_ANALYST_PROMPT,
    REPORT_ANALYST_PROMPT,
    SYSTEM_SPECIALIST_PROMPT,
    TRANSACTION_SPECIALIST_PROMPT,
)

__all__ = [
    "BUSINESS_PROCESS_ANALYST_PROMPT",
    "WORKFLOW_ANALYST_PROMPT",
    "REPORT_ANALYST_PROMPT",
    "SYSTEM_SPECIALIST_PROMPT",
    "TRANSACTION_SPECIALIST_PROMPT",
]
