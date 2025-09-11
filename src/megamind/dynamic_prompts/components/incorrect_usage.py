from megamind.dynamic_prompts.core.models import PromptVariant, SystemContext

INCORRECT_USAGE_TEXT = """
### Example 1: Missing User-Facing Content for `apply_workflow`

**This is an incorrect usage and you MUST avoid it.**

**Agent's Incorrect Response:**
<tool_code>
erpnext_mcp_tool.apply_workflow(doctype='Sales Order', name='SO-00123', action='Submit')
</tool_code>

**Why this is incorrect:** The `apply_workflow` tool was called without any user-facing content. The "Human in the Loop for State-Changing Actions" rule requires that a confirmation question and a `<function>` tag be included in the same message as the tool call.
"""


async def get_incorrect_usage_section(
    variant: PromptVariant, context: SystemContext
) -> str:
    """
    Returns the incorrect usage examples section for the agent.
    """
    return INCORRECT_USAGE_TEXT
