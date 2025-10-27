from megamind.dynamic_prompts.core.models import PromptVariant, SystemContext

PRIMARY_DIRECTIVES_TEXT = """
* **Assist Users:** Understand user requests in English or Mongolian to fetch information, find documents, create records, or update data.
* **Use Tools:** You have access to specialized tools to interact with the ERPNext system. Use them as your primary means of fulfilling requests.
* **Ensure Clarity:** If a user's request is ambiguous or lacks necessary information, ask clarifying questions before taking action.
* **Maintain Context:** Be aware of the conversation's history to handle follow-up questions effectively.
* **Discretion:** Never mention ERPNext. only refer to it as a erp system if have to.
"""


async def get_primary_directives_section(
    variant: PromptVariant, context: SystemContext
) -> str:
    """
    Returns the primary directives section for the agent.

    This component defines the core responsibilities and operational
    principles that guide the agent's behavior. It emphasizes:
    - User assistance (understanding requests in multiple languages)
    - Tool usage (primary means of fulfilling requests)
    - Clarity (asking questions when needed)
    - Context awareness (conversation history)

    Args:
        variant: The prompt variant configuration
        context: Runtime context with dynamic values

    Returns:
        Static primary directives text

    Used by variants:
        - generic
        - accounting_finance
        - Other variants that need basic operational guidelines

    Notes:
        These directives are intentionally high-level and general.
        They complement more specific instructions in other components
        like tool_usage and communication_rules.
    """
    return PRIMARY_DIRECTIVES_TEXT
