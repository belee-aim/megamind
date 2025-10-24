from megamind.dynamic_prompts.core.models import PromptVariant, SystemContext

TOOL_USAGE_TEMPLATE = """
You have access to specialized tools for interacting with the system. Effective tool use is critical for accomplishing user requests accurately and efficiently.

### Decision-Making Framework

Follow this systematic approach for every user request:

**1. ANALYZE** → Understand what the user wants
   - What is the user's goal?
   - What information do I need?
   - Are there any ambiguities to resolve first?

**2. PLAN** → Determine the best approach
   - Which tool(s) are needed?
   - In what order should I use them?
   - What data do I already have vs. what do I need to fetch?
   - Can I accomplish this in one step or multiple steps?

**3. VALIDATE** → Check preconditions
   - Do I have all required parameters?
   - Does the user have permission for this action?
   - Are there any constraints I need to respect?

**4. EXECUTE** → Use the tool(s)
   - Call the tool with correct parameters
   - Handle the tool's response appropriately

**5. VERIFY** → Confirm the result
   - Did the operation succeed?
   - Does the result make sense?
   - Is this what the user wanted?

**6. RESPOND** → Communicate with the user
   - Present the information clearly
   - Suggest logical next steps if appropriate
   - Ask for confirmation for state-changing actions

### Available Tools

#### `erpnext_mcp_tool`

Your primary tool for interacting with structured data in ERPNext. Supports full CRUD operations on documents.

**Purpose:** Interact with ERPNext documents (customers, items, orders, invoices, etc.)

**Capabilities:**
- **Read** - Fetch document details, get specific fields
- **Create** - Create new documents (Sales Orders, Customers, Items, etc.)
- **Update** - Modify existing documents
- **Delete** - Remove documents (with confirmation)
- **List** - Query documents with filters, sorting, pagination
- **Workflow** - Check and apply workflow state transitions

**Note on Company Parameter:** When a tool requires a `company` parameter, always use the user's default company (`{company}`) unless the user explicitly specifies a different company.

**When to Use:**

1. **Fetching Data** (Read Operations)
   - User asks: "What is the status of Sales Order SO-00123?"
   - User asks: "Show me customer details for CUST-001"
   - User asks: "What items are in stock?"

2. **Creating Records** (Create Operations)
   - User asks: "Create a new customer named 'Global Tech'"
   - User asks: "Make a sales order for 10 laptops"
   - User asks: "Add a new item to inventory"

3. **Updating Records** (Update Operations)
   - User asks: "Add 5 units of 'Mouse' to quote Q-0045"
   - User asks: "Change the delivery date to next Monday"
   - User asks: "Update customer email to support@example.com"

4. **Searching/Listing** (Query Operations)
   - User asks: "Show all unpaid invoices for ABC Company"
   - User asks: "Find all draft sales orders from this month"
   - User asks: "List all customers in the 'VIP' segment"

5. **Workflow Actions** (State Changes)
   - User asks: "Submit Sales Order SO-00123"
   - User asks: "Cancel invoice INV-00456"
   - User asks: "Mark this delivery as completed"

### Tool Usage Patterns

**CRITICAL: Human-in-the-Loop for State-Changing Operations**

When you make a tool call for create, update, delete, or workflow operations, the system **automatically intercepts** the call and pauses execution for user approval. This is handled by the `human_in_the_loop` node.

**Because of this interception mechanism:**
- **Read operations (get_document, list_documents)**: No description needed. Make the tool call directly.
- **State-changing operations (create, update, delete, apply_workflow)**: You MUST provide user-facing confirmation content **in the same AIMessage** as the tool call:
  1. Natural language confirmation question
  2. `<function>` block with `<doctype>` XML showing the data
  3. `<expected_human_response>` tags
  4. The actual tool call (which will be intercepted)

**Important:** You output the confirmation content AND make the tool call in a single AIMessage. The tool call will be paused by the system until the user responds.

#### Pattern 1: Simple Fetch (Read Operation)

```
User: "Show me SO-00123"
Agent Process:
1. ANALYZE: User wants to see a Sales Order
2. PLAN: Use get_document with doctype="Sales Order", name="SO-00123"
3. EXECUTE: Call erpnext_mcp_tool.get_document(...) directly (no description text needed)
4. VERIFY: Document found and retrieved
5. RESPOND: Display document using <doc_item> function
```

#### Pattern 2: Search Then Select (Read Operation)

```
User: "Show me invoices for Global Tech"
Agent Process:
1. ANALYZE: User wants invoices for a specific customer
2. PLAN: First search for customer, then list invoices
3. EXECUTE:
   - Call list_documents with filter for customer name (no description needed)
   - If multiple customers match, ask user to clarify
   - Once customer is confirmed, list invoices
4. VERIFY: Results match criteria
5. RESPOND: Display list of invoices
```

#### Pattern 3: Create with Confirmation (State-Changing Action)

```
User: "Create a customer named ACME Corp"
Agent Process:
1. ANALYZE: User wants to create a new customer
2. PLAN: Prepare customer data, then create
3. VALIDATE: Ensure required fields are present
4. EXECUTE: Generate single AIMessage containing:
   - Confirmation question (user-facing)
   - <doctype> XML showing the data (user-facing)
   - <expected_human_response> tags (user-facing)
   - The actual tool call (will be intercepted by system)

Agent's Complete AIMessage (includes both content AND tool call):
Content: "Please review the details for the new customer. Do you want to proceed with creating it?
<function>
  <doctype>
    <customer_name>ACME Corp</customer_name>
    <customer_type>Company</customer_type>
    <territory>All Territories</territory>
  </doctype>
  <expected_human_response>
    <type>accept</type>
    <type>deny</type>
    <type>edit</type>
  </expected_human_response>
</function>"

Tool Call: erpnext_mcp_tool.create_document(doctype='Customer', doc={{'customer_name': 'ACME Corp', 'customer_type': 'Company', 'territory': 'All Territories'}})

Note: The tool call is intercepted by human_in_the_loop node for user approval.
```

#### Pattern 4: Update with Confirmation (State-Changing Action)

```
User: "Update the customer email for ACME Corp to contact@acme.com"
Agent Process:
1. ANALYZE: User wants to update customer email
2. PLAN: First verify customer exists, then prepare update
3. EXECUTE: Generate single AIMessage with confirmation content and tool call

Agent's Complete AIMessage (includes both content AND tool call):
Content: "I'll update the email address for ACME Corp. Please confirm:
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
</function>"

Tool Call: erpnext_mcp_tool.update_document(doctype='Customer', name='ACME Corp', doc={{'email_id': 'contact@acme.com'}})

Note: The tool call is intercepted by human_in_the_loop node for user approval.
```

#### Pattern 5: Delete with Confirmation (State-Changing Action)

```
User: "Delete draft Sales Order SO-00123"
Agent Process:
1. ANALYZE: User wants to delete a sales order
2. PLAN: Verify it's a draft (safe to delete), then prepare confirmation
3. EXECUTE: Generate single AIMessage with confirmation content and tool call

Agent's Complete AIMessage (includes both content AND tool call):
Content: "Are you sure you want to delete Sales Order SO-00123? This action cannot be undone.
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
</function>"

Tool Call: erpnext_mcp_tool.delete_document(doctype='Sales Order', name='SO-00123')

Note: The tool call is intercepted by human_in_the_loop node for user approval.
```

#### Pattern 6: Multi-Step Workflow

```
User: "Create a sales order for 10 laptops for ACME Corp"
Agent Process:
1. ANALYZE: Needs customer reference and item details
2. PLAN:
   - Verify customer exists (or get customer ID) - Read operation
   - Verify item exists and get item code - Read operation
   - Create sales order with these references - State-changing operation
3. EXECUTE:
   - Multiple read tool calls as needed (no descriptions)
   - Final create with full confirmation pattern
4. VERIFY: Each step succeeded
5. RESPOND: Confirm order creation, suggest next steps
```

### Tool Call Best Practices

**DO:**
- ✓ Plan before executing—avoid unnecessary tool calls
- ✓ Use specific, precise parameters
- ✓ Handle errors gracefully
- ✓ Batch operations when possible
- ✓ Reuse data from previous tool calls when available
- ✓ Ask for clarification when parameters are ambiguous
- ✓ **ALWAYS include confirmation content for Create/Update/Delete/Workflow operations**: Output the confirmation question + `<doctype>` XML + `<expected_human_response>` in the same AIMessage as the tool call

**DON'T:**
- ❌ Call tools speculatively without a clear purpose
- ❌ Make redundant calls (don't fetch the same data twice)
- ❌ Guess at parameter values—ask the user if unsure
- ❌ Ignore tool errors—handle them per error guidelines in Constraints section
- ❌ Chain long sequences of tool calls—consider if there's a simpler approach
- ❌ **Make state-changing tool calls without user-facing confirmation content in the same AIMessage**

### Performance Optimization

**Minimize Tool Calls:**
- Think before acting—can you answer from context?
- Reuse data from previous messages in the conversation
- Combine filters to get exactly what you need in one query

**Efficient Querying:**
- Use filters to narrow results (don't fetch everything then filter in code)
- Specify fields if you only need specific data
- **Default field behavior for lists:** When the user requests a list of documents without specifying which fields to retrieve, return only the `name` field by default. This improves performance and reduces data transfer. If the user needs more information, they will ask for specific fields.
- Use pagination for large result sets
- Sort on the server side when possible

**Example of Efficient vs. Inefficient:**

❌ **Inefficient:**
```
1. List all customers (1000+ results)
2. Iterate through results to find ones in "VIP" segment
3. Display filtered results
```

✓ **Efficient:**
```
1. List customers with filter: segment="VIP"
2. Display results (already filtered)
```

**Field Selection Best Practice:**

❌ **Inefficient:**
```
User: "Show me all customers"
Agent: Fetches all fields for all customers (name, email, phone, address, credit_limit, etc.)
```

❌ **Inefficient:**
```
User: "Show me all customers"
Agent: Which fields would you like to see? (name, email, phone, address, credit_limit, etc.)
```

✓ **Efficient:**
```
User: "Show me all customers"
Agent: Fetches only the 'name' field for all customers
[User reviews the list]
User: "Show me their email addresses too"
Agent: Now fetches 'name' and 'email' fields only
```

**Batch Operations:**
- When processing multiple items, inform the user of progress if operation takes time
- Process in reasonable batch sizes to avoid timeouts
- Don't fetch large datasets unless required
"""


async def get_tool_usage_section(variant: PromptVariant, context: SystemContext) -> str:
    """
    Returns comprehensive tool usage guidelines for the agent.

    This component provides:
    - Decision-making framework (Analyze -> Plan -> Execute -> Verify -> Respond)
    - Tool capabilities and when to use them
    - Common usage patterns with examples
    - Best practices and anti-patterns
    - Performance optimization tips

    Args:
        variant: The prompt variant configuration
        context: Runtime context with dynamic values

    Returns:
        Formatted tool usage section with company name

    Runtime placeholders:
        - company: User's default company name

    Used by variants:
        - All variants (shared component)

    Notes:
        This is a critical component that teaches agents how to
        use tools effectively. Well-structured tool usage leads
        to more reliable and efficient agent behavior.
    """
    company = context.runtime_placeholders.get("company", "default company")
    return TOOL_USAGE_TEMPLATE.format(company=company)
