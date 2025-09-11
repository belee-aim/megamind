from megamind.dynamic_prompts.core.models import PromptVariant, SystemContext

AGENT_ROLE_TEMPLATE = """
You are **Бараа материалын хөдөлгөөн хийдэг**, an intelligent assistant responsible for managing material transfers between warehouses inside ERPNext for the company `{company}`.
"""


async def get_agent_role_section(variant: PromptVariant, context: SystemContext) -> str:
    """
    Returns the specialized agent role for the stock movement agent.
    """
    company = context.runtime_placeholders.get("company", "the company")
    return AGENT_ROLE_TEMPLATE.format(company=company)
