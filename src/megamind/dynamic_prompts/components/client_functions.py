from megamind.dynamic_prompts.core.models import PromptVariant, SystemContext

CLIENT_FUNCTIONS_TEXT = """
When you need to display a list of items or the details of a specific doctype, you must use the following XML format. **Before outputting the `<function>` XML, you must always provide a brief, one-sentence natural language description of what you are showing.** The client-side application will parse this XML and render the appropriate UI components.

### 6.1. List Function

To display a list of items, use the `<list>` tag inside a `<function>` tag. Each item in the list should be enclosed in a `<list_item>` tag.

**Example:**

<function>
  <render_list>
    <title>Sales Order</title>
    <description>List of all sales orders</description>
    <list>
      <list_item>Sales Order SO-0001</list_item>
      <list_item>Sales Order SO-0002</list_item>
      <list_item>Sales Order SO-0003</list_item>
    </list>
  </render_list>
</function>

### 6.2. Doctype Function

Use the `<doctype>` tag to display **partial, static information** that you have already retrieved. Each field of the doctype should be represented by a tag with the field's name.

**Note:** This function should only be used for displaying partial information. For displaying full details, please use the `doc_item` function.

**Example:**

<function>
  <doctype>
    <name>SO-0001</name>
    <customer>John Doe</customer>
    <status>Draft</status>
    <total_amount>100.00</total_amount>
  </doctype>
</function>

### 6.3. Doc Item Function

Use the `<doc_item>` tag to display the **full, real-time details** of a document. This function signals the client-side application to fetch and render the complete data for the specified document. This is the preferred method for showing complete information as it ensures the data is always up-to-date.

**Example:**

<function>
  <doc_item>
    <doctype>Stock Entry</doctype>
    <name>MAT-STE-2025-00012</name>
  </doc_item>
</function>

"""


async def get_client_functions_section(
    variant: PromptVariant, context: SystemContext
) -> str:
    """
    Returns the client-side functions section for the agent.

    This component teaches the agent how to use special XML formats
    that the client application parses to render UI components. It covers:
    - <render_list> for displaying lists of items
    - <doctype> for showing partial/static document data
    - <doc_item> for triggering full real-time document display

    Args:
        variant: The prompt variant configuration
        context: Runtime context with dynamic values

    Returns:
        Static client functions documentation

    Used by variants:
        - All variants (shared component)

    Notes:
        This is a critical component that ensures agents format their
        responses correctly for the client UI. The XML formats are
        parsed by the frontend to create rich, interactive displays.
    """
    return CLIENT_FUNCTIONS_TEXT
