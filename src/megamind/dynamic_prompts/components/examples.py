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

### Example 4: Handling Workflow State Change

**User:** "Change the status of Sales Order SO-00123 to 'To Deliver and Bill'."

**Agent's Internal Monologue:**
1.  The user wants to change the workflow state of a Sales Order.
2.  First, I need to check the available workflow actions for this document. I will use the `get_workflow_state` tool.
3.  *Tool returns available transitions: `['To Deliver and Bill', 'Cancelled']`.*
4.  The requested state 'To Deliver and Bill' is a valid transition.
5.  My instructions require me to ask for confirmation before applying a workflow change.
6.  I will construct the `apply_workflow` tool call.
7.  I will also construct the user-facing content, which includes a confirmation question.
8.  I will output these two parts in a single `AIMessage`.

**Agent's Final Response to User (This is a single AIMessage containing the user-facing text and the tool_call):**

Are you sure you want to change the status of Sales Order SO-00123 to 'To Deliver and Bill'?
<function>
  <doctype>
    <name>SO-00123</name>
    <status>To Deliver and Bill</status>
  </doctype>
  <expected_human_response>
    <type>accept</type>
    <type>deny</type>
  </expected_human_response>
</function>

<tool_code>
erpnext_mcp_tool.apply_workflow(doctype='Sales Order', name='SO-00123', action='To Deliver and Bill')
</tool_code>

### Example 5: Handling "Next State" Workflow Change

**User:** "Move Sales Order SO-00123 to the next stage."

**Agent's Internal Monologue:**
1.  The user wants to advance the workflow for Sales Order SO-00123 but hasn't specified the next state.
2.  I need to determine the current state and the available transitions. I will use the `get_workflow_state` tool.
3.  *Tool returns current state as 'Draft' and available transitions: `['Submit', 'Cancel']`.*
4.  The most logical "next stage" from 'Draft' is 'Submit'.
5.  My instructions require me to ask for confirmation before applying a workflow change.
6.  I will construct the `apply_workflow` tool call with the action 'Submit'.
7.  I will also construct the user-facing content, which includes a confirmation question specifying the action.
8.  I will output these two parts in a single `AIMessage`.

**Agent's Final Response to User (This is a single AIMessage containing the user-facing text and the tool_call):**

The next stage for Sales Order SO-00123 is 'Submit'. Are you sure you want to proceed?
<function>
  <doctype>
    <name>SO-00123</name>
    <status>Submit</status>
  </doctype>
  <expected_human_response>
    <type>accept</type>
    <type>deny</type>
  </expected_human_response>
</function>

<tool_code>
erpnext_mcp_tool.apply_workflow(doctype='Sales Order', name='SO-00123', action='Submit')
</tool_code>

### Example 6: Proactive Workflow Suggestion

**User:** "Show me the details for Sales Order SO-00124."

**Agent's Internal Monologue:**
1.  The user wants to see the details for Sales Order SO-00124.
2.  I will use the `get_document` tool to fetch the data for SO-00124.
3.  *Tool returns the document details, including `workflow_state: 'Draft'`.*
4.  Since the document has a workflow state, I should check for available transitions to be proactive. I will use the `get_workflow_state` tool.
5.  *Tool returns available transitions: `['Submit', 'Cancel']`.*
6.  The most logical next step is 'Submit'. I will display the document details as requested, but also ask the user if they want to submit it.
7.  I will construct the response with the `<doc_item>` function to show the details and add a clear, actionable question with `expected_human_response`.

**Agent's Final Response to User:**
Here are the details for Sales Order SO-00124. The current status is 'Draft'. Would you like to submit it?
<function>
  <doc_item>
    <doctype>Sales Order</doctype>
    <name>SO-00124</name>
    <status>Draft</status>
    <next_status>Submit</next_status>
  </doc_item>
</function>
"""


async def get_examples_section(variant: PromptVariant, context: SystemContext) -> str:
    """
    Returns the few-shot examples section for the agent.
    """
    return EXAMPLES_TEXT
