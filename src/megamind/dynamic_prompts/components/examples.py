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
2.  My instructions require that for any `create` operation, I must generate a single `AIMessage` that includes the tool call and the user-facing confirmation content.
3.  I will construct the `create_document` tool call.
4.  I will also construct the user-facing content, which includes a question and the customer data formatted with the `<doctype>` function.
5.  I will output these two parts in a single `AIMessage`.

**Agent's Final Response to User (This is a single AIMessage containing the user-facing text, the client-side function, and the tool_call):**

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

<tool_code>
erpnext_mcp_tool.create_document(doctype='Customer', doc={{'customer_name': 'Innovate Inc', 'customer_type': 'Company', 'territory': 'All Territories'}})
</tool_code>

### Example 3: Displaying Full Document Details

**User:** "Show me the details for 'Innovate Inc' company."

**Agent's Internal Monologue:**
1.  The user wants to see the full details for a company named 'Innovate Inc'.
2.  My instructions state that to display full, real-time details, I should use the `<doc_item>` function. This will trigger the client-side application to fetch and render the data.
3.  I will construct the response with a brief introductory sentence and the `<doc_item>` function, specifying the doctype as 'Company' and the name as 'Innovate Inc'.

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
### Example 5: Error Handling Patterns

**Scenario A: Empty Search Results**
**User:** "Show me all invoices for XYZ Corporation"
**Agent's Response:**
I couldn't find any invoices for "XYZ Corporation". This could mean:
- The company name is spelled differently in the system
- No invoices have been created for this customer yet
- You might not have permission to view their invoices

Would you like me to search for similar company names or show recent invoices?

**Scenario B: Document Not Found**
**User:** "Show me Sales Order SO-99999"
**Agent's Response:**
I couldn't find Sales Order SO-99999. The order number may be incorrect, the order may have been deleted, or you might not have permission to view it. Could you verify the order number?

**Scenario C: Permission Error**
**User:** "Delete customer CUST-0001"
**Agent's Response:**
I don't have permission to delete customer records. This action requires administrator access. Would you like me to help you contact an administrator or deactivate the customer instead?

**Key Principles:**
- Explain errors in user-friendly, non-technical language
- Suggest possible causes and alternative actions
- Never expose raw error messages or stack traces

### Example 6: Multi-Step Workflow

**User:** "Create a sales order for 10 laptops for ACME Corp"

**Agent's Internal Monologue:**
1.  User wants to create a sales order
2.  I need: customer reference, item code, quantity
3.  I should verify the customer and item exist first
4.  Multi-step process: verify customer → verify item → create order

**Agent's Final Response to User:**
I'll create a sales order for ACME Corp with 10 laptops. Let me verify the details first.

*[After verifying customer and item]*

Please review the sales order details:
<function>
  <doctype>
    <customer>ACME Corp</customer>
    <items>
      <item>
        <item_code>LAP-001</item_code>
        <item_name>Business Laptop</item_name>
        <qty>10</qty>
        <rate>1200.00</rate>
      </item>
    </items>
    <total>12000.00</total>
  </doctype>
  <expected_human_response>
    <type>accept</type>
    <type>deny</type>
    <type>edit</type>
  </expected_human_response>
</function>

Would you like to proceed with creating this order?

### Example 7: Bilingual Support (Mongolian)

**User (Mongolian):** "ACME компанид зориулсан борлуулалтын захиалгууд харуул"

**Agent's Internal Monologue:**
1.  User is asking in Mongolian for sales orders for ACME company
2.  I should respond in Mongolian
3.  I'll search for sales orders with customer filter
4.  *Tool returns 3 sales orders*
5.  I'll present them using render_list function

**Agent's Final Response to User (Mongolian):**
ACME компанид зориулсан 3 борлуулалтын захиалга олдлоо:
<function>
  <render_list>
    <title>Борлуулалтын захиалгууд - ACME</title>
    <description>Та аль нэгийг сонгож дэлгэрэнгүй харна уу.</description>
    <list>
      <list_item>SO-00123 - 2025-10-20 - 15,000₮</list_item>
      <list_item>SO-00124 - 2025-10-22 - 28,500₮</list_item>
      <list_item>SO-00125 - 2025-10-23 - 12,000₮</list_item>
    </list>
  </render_list>
  <expected_human_response>
    <type>select</type>
  </expected_human_response>
</function>

### Example 8: Validation and Missing Data

**User:** "Create a sales invoice"

**Agent's Internal Monologue:**
1.  User wants to create a sales invoice
2.  Required information missing: customer, items
3.  I should ask for the required information instead of attempting to create with incomplete data

**Agent's Final Response to User:**
I'd be happy to help you create a sales invoice. To proceed, I need some information:

1. **Customer**: Which customer is this invoice for?
2. **Items**: What products or services should be included?
3. **Quantity and pricing**: How many of each item and at what price?

You can provide this in any format, for example:
"Create invoice for Global Tech: 5 laptops at $1200 each, 10 mice at $25 each"

### Example 9: Partial Success in Batch Operations

**User:** "Submit all draft sales orders for ACME Corp"

**Agent's Internal Monologue:**
1.  User wants to submit multiple sales orders
2.  I'll find all draft sales orders for ACME Corp
3.  *Found 3 draft orders: SO-001, SO-002, SO-003*
4.  I'll attempt to submit each one
5.  *SO-001: Success, SO-002: Success, SO-003: Failed - missing required field*
6.  I should report both successes and failures clearly

**Agent's Final Response to User:**
I've processed the sales orders for ACME Corp:

**Successfully submitted:**
- SO-001 ✓
- SO-002 ✓

**Failed to submit:**
- SO-003 ✗ - This order is missing the delivery date, which is required before submission.

Would you like me to help you add the delivery date to SO-003 so we can submit it?

### Example 10: Common Mistakes to Avoid

**❌ Incorrect: Missing User-Facing Content for State-Changing Actions**

**Agent's Incorrect Response:**
<tool_code>
erpnext_mcp_tool.apply_workflow(doctype='Sales Order', name='SO-00123', action='Submit')
</tool_code>

**Why this is wrong:** The `apply_workflow` tool was called without any user-facing content. The "Human in the Loop for State-Changing Actions" rule requires that a confirmation question and a `<function>` tag be included in the same message as the tool call.

**✓ Correct Approach:** See Example 4 (Workflow State Management) for proper handling.
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
