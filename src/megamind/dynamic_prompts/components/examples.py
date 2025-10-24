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

### Example 2B: Update Operation with Confirmation

**User:** "Update the email for customer ACME Corp to contact@acme.com"

**Agent's Internal Monologue:**
1.  The user wants to update the email for customer ACME Corp
2.  This is a state-changing action (update), so I must generate a single AIMessage with the confirmation content AND the tool call
3.  The tool call will be intercepted by the system for user approval

**Agent's Final Response to User (This is a single AIMessage containing BOTH the content AND the tool call):**

Content (what the user sees):
I'll update the email address for ACME Corp. Please confirm:
<function>
  <doctype>
    <customer_name>ACME Corp</customer_name>
    <email_id>contact@acme.com</email_id>
  </doctype>
  <expected_human_response>
    <type>accept</type>
    <type>deny</type>
    <type>edit</type>
  </expected_human_response>
</function>

Tool Call (intercepted by system for approval):
erpnext_mcp_tool.update_document(doctype='Customer', name='ACME Corp', doc={{'email_id': 'contact@acme.com'}})

### Example 2C: Delete Operation with Confirmation

**User:** "Delete draft Sales Order SO-00123"

**Agent's Internal Monologue:**
1.  The user wants to delete a sales order
2.  This is a destructive state-changing action, so I must generate a single AIMessage with the confirmation content AND the tool call
3.  I should verify it's a draft (safer to delete) and show clear warning
4.  The tool call will be intercepted by the system for user approval

**Agent's Final Response to User (This is a single AIMessage containing BOTH the content AND the tool call):**

Content (what the user sees):
Are you sure you want to delete Sales Order SO-00123? This action cannot be undone.
<function>
  <doctype>
    <name>SO-00123</name>
    <customer>Global Tech</customer>
    <status>Draft</status>
    <total>$12,000</total>
  </doctype>
  <expected_human_response>
    <type>accept</type>
    <type>deny</type>
  </expected_human_response>
</function>

Tool Call (intercepted by system for approval):
erpnext_mcp_tool.delete_document(doctype='Sales Order', name='SO-00123')

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

### Example 7: List Operations with Progressive Field Disclosure

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
- User can always ask for more details

### Example 8: Bilingual Support (Mongolian)

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

### Example 9: Validation and Missing Data

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

### Example 10: Partial Success in Batch Operations

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

### Example 11: Common Mistakes to Avoid

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
