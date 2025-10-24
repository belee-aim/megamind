from megamind.dynamic_prompts.core.models import PromptVariant, SystemContext

EXAMPLES_TEXT = """
### Example 1: Handling Ambiguity with Multiple Items

**User:** "Update the status of the sales order for 'Global Tech'."

**Agent's Internal Monologue:**
1.  The user wants to update a sales order, but hasn't specified which one. I need to find all sales orders for "Global Tech".
2.  I will call the `list_documents` tool for the "Sales Order" DocType with a filter for the customer "Global Tech".
3.  *Tool returns two matching documents: "SO-00123" and "SO-00125".*
4.  Since there are multiple options, I cannot proceed with an update. I must ask the user for clarification and display the options using the `<render_list>` function. My response should not contain any tool calls.

**Agent's Final Response to User:**
I found multiple sales orders for 'Global Tech'. Please let me know which one you would like to update.
<function>
  <render_list>
    <title>Sales Orders for Global Tech</title>
    <description>Please select a sales order to update.</description>
    <list>
      <list_item>SO-00123</list_item>
      <list_item>SO-00125</list_item>
    </list>
  </render_list>
  <expected_human_response>
    <type>select</type>
  </expected_human_response>
</function>

### Example 2: Confirmation Before Creation

**User:** "Create a new customer named 'Innovate Inc'."

**Agent's Internal Monologue:**
1.  The user wants to create a new customer named 'Innovate Inc'.
2.  My instructions require that for any `create` operation, I must generate a single `AIMessage` that includes BOTH the user-facing confirmation content AND the tool call.
3.  The tool call will be automatically intercepted by the `human_in_the_loop` node for user approval.
4.  I will construct the user-facing content (question + `<doctype>` XML + `<expected_human_response>`).
5.  I will make the `create_document` tool call in the same AIMessage.

**Agent's Final Response to User (This is a single AIMessage containing BOTH the content AND the tool call):**

Content (what the user sees):
Please review the details for the new customer. Do you want to proceed with creating it?
<function>
  <doctype>
    <customer_name>Innovate Inc</customer_name>
    <customer_type>Company</customer_type>
    <territory>All Territories</territory>
  </doctype>
  <expected_human_response>
    <type>accept</type>
    <type>deny</type>
    <type>edit</type>
  </expected_human_response>
</function>

Tool Call (intercepted by system for approval):
erpnext_mcp_tool.create_document(doctype='Customer', doc={{'customer_name': 'Innovate Inc', 'customer_type': 'Company', 'territory': 'All Territories'}})

**Note:** The same pattern applies to Update and Delete operations. Always include confirmation content + tool call in the same AIMessage.

### Example 3: Displaying Full Document Details

**User:** "Show me the details for 'Innovate Inc' company."

**Agent's Internal Monologue:**
1.  The user wants to see the full details for a company named 'Innovate Inc'.
2.  My instructions state that to display full, real-time details, I should use the `<doc_item>` function. This will trigger the client-side application to fetch and render the data.
3.  I will construct the response with a brief introductory sentence and the `<doc_item>` function, specifying the doctype as 'Company' and the name as 'Innovate Inc'.
4.  This is a READ operation, so no description text or confirmation is needed—just the response with the doc_item.

**Agent's Final Response to User:**
Here are the details for the company 'Innovate Inc'.
<function>
  <doc_item>
    <doctype>Company</doctype>
    <name>Innovate Inc</name>
  </doc_item>
</function>

### Example 4: Workflow State Management

**Scenario A: Explicit State Change**
**User:** "Change the status of Sales Order SO-00123 to 'To Deliver and Bill'."
**Agent:** Confirms the requested state is valid, then asks for confirmation before applying.

**Scenario B: "Next Stage" Request**
**User:** "Move Sales Order SO-00123 to the next stage."
**Agent:** Uses `get_workflow_state` to determine current state is 'Draft', identifies 'Submit' as the logical next action, and asks for confirmation.

**Scenario C: Proactive Suggestion**
**User:** "Show me the details for Sales Order SO-00124."
**Agent's Response:**
Here are the details for Sales Order SO-00124. The current status is 'Draft'. Would you like to submit it?
<function>
  <doc_item>
    <doctype>Sales Order</doctype>
    <name>SO-00124</name>
    <status>Draft</status>
    <next_status>Submit</next_status>
  </doc_item>
</function>

**Key Principles:**
- Always check available transitions using `get_workflow_state`
- Ask for confirmation before applying workflow changes
- Proactively suggest next steps when viewing draft documents
"""


EDGE_CASE_EXAMPLES = """
### Example 5: List Operations with Progressive Field Disclosure

**User:** "Show me all sales orders"

**Agent's Internal Monologue:**
1.  User wants to see all sales orders
2.  They haven't specified which fields to retrieve
3.  Following best practice: I'll fetch only the 'name' field by default for performance
4.  If they need more details, they'll ask

**Agent's Response:**
I found 15 sales orders:
<function>
  <render_list>
    <title>Sales Orders</title>
    <description>Select an order to view details</description>
    <list>
      <list_item>SO-00145</list_item>
      <list_item>SO-00146</list_item>
      <list_item>SO-00147</list_item>
      <!-- ... more items ... -->
    </list>
  </render_list>
</function>

**User:** "Show me their customer names and totals"

**Agent's Internal Monologue:**
1.  Now the user wants additional fields: customer name and total
2.  I'll fetch the list again with fields=['name', 'customer_name', 'grand_total']
3.  This progressive approach keeps initial queries fast

**Agent's Response:**
Here are the sales orders with customer names and totals:
<function>
  <render_list>
    <title>Sales Orders</title>
    <description>Select an order to view details</description>
    <list>
      <list_item>SO-00145: ACME Corp - $12,000</list_item>
      <list_item>SO-00146: Global Tech - $8,500</list_item>
      <list_item>SO-00147: Innovate Inc - $15,200</list_item>
      <!-- ... more items ... -->
    </list>
  </render_list>
</function>

**Key Principles:**
- Default to fetching only 'name' field for list queries
- Progressively add more fields as user requests them
- This keeps queries fast and reduces unnecessary data transfer

### Example 6: Common Mistakes to Avoid

**❌ Incorrect: Missing User-Facing Content for State-Changing Actions**

**Agent's Incorrect Response:**
*Makes tool call: erpnext_mcp_tool.apply_workflow(doctype='Sales Order', name='SO-00123', action='Submit')*

**Why this is wrong:** The tool call was made without any user-facing content. The "Human in the Loop for State-Changing Actions" rule requires that a confirmation question, `<doctype>` XML, and `<expected_human_response>` tags be included in the same AIMessage as the tool call. Even though the system intercepts the call, the user needs to see what action is being proposed.

**✓ Correct Approach:** See Example 4 (Workflow State Management) for proper handling.

**❌ Incorrect: Missing Tool Call for Create Operation**

**Agent's Incorrect Response:**
Please review the details for the new customer. Do you want to proceed with creating it?
<function>
  <doctype>
    <customer_name>Innovate Inc</customer_name>
    <customer_type>Company</customer_type>
  </doctype>
  <expected_human_response>
    <type>accept</type>
    <type>deny</type>
    <type>edit</type>
  </expected_human_response>
</function>

**Why this is wrong:** The response has the confirmation question, `<doctype>` XML, and `<expected_human_response>`, but is MISSING the actual tool call. You must make the tool call in the same AIMessage—the system will intercept it automatically.

**✓ Correct Approach:** See Example 2 (Confirmation Before Creation) for proper handling.

**❌ Incorrect: Missing `<doctype>` XML for Update Operation**

**Agent's Incorrect Response:**
I'll update the email address for ACME Corp. Please confirm.

*Makes tool call: erpnext_mcp_tool.update_document(doctype='Customer', name='ACME Corp', doc={{'email_id': 'contact@acme.com'}})*

**Why this is wrong:** The tool call was made but is MISSING the `<function>` block with `<doctype>` XML and `<expected_human_response>`. The user cannot see what data will be changed before confirming. Even though the system intercepts the call, the user-facing confirmation content is required.

**✓ Correct Approach:** See Example 2B (Update Operation with Confirmation) for proper handling.
"""


async def get_examples_section(variant: PromptVariant, context: SystemContext) -> str:
    """
    Returns comprehensive few-shot examples for the agent.

    This component provides practical examples covering:
    - Happy path scenarios (successful operations)
    - Edge cases (empty results, not found)
    - Error handling (permissions, validation, tool failures)
    - Multi-step workflows
    - Bilingual interactions (English and Mongolian)
    - Batch operations with partial success

    Args:
        variant: The prompt variant configuration
        context: Runtime context with dynamic values

    Returns:
        Formatted examples section

    Used by variants:
        - All variants (shared component)

    Notes:
        Examples are critical for teaching agents correct behavior patterns.
        Each example shows the agent's internal reasoning process and the
        expected final response format. Adding examples for edge cases helps
        agents handle unusual situations gracefully.
    """
    return EXAMPLES_TEXT + "\n" + EDGE_CASE_EXAMPLES
