from megamind.dynamic_prompts.core.models import PromptVariant, SystemContext

AGENT_ROLE_TEMPLATE = """
You are Aimlink Agent, a professional and highly capable AI assistant for `{company}`, integrated with the user's business systems. Your primary role is to help users interact with their ERPNext system efficiently and accurately. Act as an expert system user who is always helpful, clear, and concise.

**IMPORTANT**: When using any tool that requires a `company` parameter, you MUST always use the default company: `{company}`. Do not ask the user for the company name.
"""


async def get_agent_role_section(variant: PromptVariant, context: SystemContext) -> str:
    """
    Returns the generic agent role section.

    This component defines the basic identity and purpose of the
    generic Aimlink Agent. It's used for the general-purpose variant
    that doesn't have specialized domain knowledge.

    Args:
        variant: The prompt variant configuration
        context: Runtime context with dynamic values

    Returns:
        Formatted agent role text with company name

    Runtime placeholders:
        - company: User's default company name

    Used by variants:
        - generic (primary use case)

    Notes:
        This is the default agent role. Specialized variants like
        accounting_finance or stock_movement use their own
        variant-specific agent role components instead.
    """
    company = context.runtime_placeholders.get("company", "default company")
    return AGENT_ROLE_TEMPLATE.format(company=company)
