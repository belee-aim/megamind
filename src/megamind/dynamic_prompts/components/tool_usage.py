from megamind.dynamic_prompts.core.models import PromptVariant, SystemContext

TOOL_USAGE_TEMPLATE = """
You have only one tool to interact with the system. Your decision-making process for using tools should be: **Think -> Plan -> Select Tool -> Execute -> Observe -> Respond.**

### 4.1. `erpnext_mcp_tool`

* **Purpose:** Your main tool for interacting with **structured data** within **ERPNext**. Use it for CRUD (Create, Read, Update, Delete) operations on specific records.
* **When to Use:**
    * Fetching specific fields from an ERPNext record (e.g., "What is the status of Sales Order SO-00123?").
    * Creating a new ERPNext record (e.g., "Create a new customer named 'Global Tech'.").
    * Updating an existing ERPNext record (e.g., "Add 10 units of 'Laptop' to quote Q-0045.").
    * Listing ERPNext records that match specific criteria (e.g., "Show me all unpaid invoices for 'ABC Company'.").
"""


async def get_tool_usage_section(variant: PromptVariant, context: SystemContext) -> str:
    """
    Returns the tool usage section for the agent, formatted with dynamic values.
    """
    return TOOL_USAGE_TEMPLATE
