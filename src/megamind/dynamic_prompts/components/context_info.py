from megamind.dynamic_prompts.core.models import PromptVariant, SystemContext

CONTEXT_INFO_TEMPLATE = """**Current Date and Time**: {current_datetime}"""


async def get_context_info_section(variant: PromptVariant, context: SystemContext) -> str:
    """
    Returns the current context information including date and time.

    This component provides temporal context to the LLM, helping it understand
    when the conversation is taking place and enabling time-aware responses.

    Args:
        variant: The prompt variant configuration
        context: Runtime context with dynamic values

    Returns:
        Formatted context information with current datetime

    Runtime placeholders:
        - current_datetime: Current date and time in format "YYYY-MM-DD HH:MM:SS TZ"

    Used by variants:
        - generic
        - stock_movement
        - accounting_finance

    Notes:
        This component should typically appear at the very beginning of the
        system prompt to immediately establish temporal context.
    """
    current_datetime = context.runtime_placeholders.get(
        "current_datetime", "Not available"
    )
    return CONTEXT_INFO_TEMPLATE.format(current_datetime=current_datetime)
