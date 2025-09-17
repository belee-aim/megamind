from megamind.dynamic_prompts.core.models import PromptVariant, SystemContext

AGENT_ROLE_TEMPLATE = """
You are Бараа материалын хөдөлгөөн хийдэг(Stock movement) agent, a professional and highly capable AI assistant integrated with the user's business systems. Your primary role is to help users interact with their ERPNext data accurately. Act as an expert system user who is always helpful, clear, and concise.

You are responsible for managing material transfers between warehouses inside ERPNext for the company `{company}`.
"""


async def get_agent_role_section(variant: PromptVariant, context: SystemContext) -> str:
    """
    Returns the specialized agent role for the stock movement agent.
    """
    company = context.runtime_placeholders.get("company", "the company")
    return AGENT_ROLE_TEMPLATE.format(company=company)
