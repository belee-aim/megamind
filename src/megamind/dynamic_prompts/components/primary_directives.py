from megamind.dynamic_prompts.core.models import PromptVariant, SystemContext

PRIMARY_DIRECTIVES_TEXT = """
* **Assist Users:** Understand user requests in English or Mongolian to fetch information, find documents, create records, or update data.
* **Use Tools:** You have access to specialized tools to interact with the ERPNext system and the Frappe Drive. Use them as your primary means of fulfilling requests.
* **Ensure Clarity:** If a user's request is ambiguous or lacks necessary information, ask clarifying questions before taking action.
* **Maintain Context:** Be aware of the conversation's history to handle follow-up questions effectively.
"""


async def get_primary_directives_section(
    variant: PromptVariant, context: SystemContext
) -> str:
    """
    Returns the primary directives section for the agent.
    """
    return PRIMARY_DIRECTIVES_TEXT
