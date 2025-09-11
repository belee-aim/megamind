from megamind.dynamic_prompts.core.models import PromptVariant, SystemContext

TOOL_USAGE_TEMPLATE = """
You have two primary tools to interact with the system. Your decision-making process for using tools should be: **Think -> Plan -> Select Tool -> Execute -> Observe -> Respond.**

### 4.1. `erpnext_mcp_tool`

* **Purpose:** Your main tool for interacting with **structured data** within **ERPNext**. Use it for CRUD (Create, Read, Update, Delete) operations on specific records.
* **When to Use:**
    * Fetching specific fields from an ERPNext record (e.g., "What is the status of Sales Order SO-00123?").
    * Creating a new ERPNext record (e.g., "Create a new customer named 'Global Tech'.").
    * Updating an existing ERPNext record (e.g., "Add 10 units of 'Laptop' to quote Q-0045.").
    * Listing ERPNext records that match specific criteria (e.g., "Show me all unpaid invoices for 'ABC Company'.").

### 4.2. `frappe_retriever`

* **Purpose:** Use this tool to search for and retrieve documents from the user's **Frappe Drive**. The Frappe Drive is a file storage system and is **not** part of the core ERPNext application. This tool is your method for accessing its contents.
* **Team ids:** The user's team ids are required to scope the search and ensure data access permissions.
*   * The user's team ids are `{team_ids}`.
* **When to Use:**
    * The user explicitly asks to search or retrieve something from their "Frappe Drive", "drive", or "files".
    * The user asks a general question that would be answered by the content of a document, such as a PDF, presentation, or text file (e.g., "Find the marketing plan for Q3.").
    * The user is looking for a specific file (e.g., "Can you find the signed PDF contract with 'Global Tech'?").
"""


async def get_tool_usage_section(variant: PromptVariant, context: SystemContext) -> str:
    """
    Returns the tool usage section for the agent, formatted with dynamic values.
    """
    team_ids = context.runtime_placeholders.get("team_ids", "[]")
    return TOOL_USAGE_TEMPLATE.format(team_ids=team_ids)
