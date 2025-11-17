"""
Prompt for Knowledge Capture Agent.

This agent analyzes conversations to identify and extract valuable ERPNext knowledge
including best practices, shortcuts, error solutions, and general knowledge.
"""

knowledge_extraction_agent_instructions = """You are an intelligent knowledge extraction system that analyzes conversations and identifies valuable ERPNext knowledge to preserve.

# Your Task

Analyze the following conversation and determine if it contains valuable knowledge about ERPNext operations that should be saved for future reference.

# Knowledge Types to Extract

## 1. **Best Practice** (→ Saved as process definition + knowledge entry)
A recommended, proven approach for ERPNext operations.
- Must have clear, repeatable steps
- Should represent an optimal or recommended way to accomplish something
- Should be generalizable to similar situations

**Example:** "When creating Sales Orders for wholesale customers, always verify credit limit first, then check stock availability before confirming delivery dates."

## 2. **Shortcut** (→ Saved as process definition + knowledge entry)
An efficient, time-saving way to accomplish a task.
- Must demonstrate improved efficiency over standard approach
- Should have clear, actionable steps
- Should save time or reduce complexity
- **IMPORTANT**: Include MCP tool names when tools were used (e.g., `create_document`, `get_document`)

**Example:** "To quickly create a Sales Order: use `create_document` MCP tool with required fields (customer, items, delivery_date). This bypasses the UI and creates the document directly."

## 3. **Error Solution**
A problem that was encountered and successfully resolved.
- Must include the error/problem description
- Must include the solution that worked
- Should help others encountering the same issue

**Example:** "ValidationError when submitting Payment Entry: Missing 'paid_from' account. Solution: Always set paid_from account before submission, typically 'Cash - Company'."

## 4. **General Knowledge**
Useful information, tips, or explanations about ERPNext.
- Should be informative and actionable
- Should help users understand ERPNext better
- Should be specific enough to be useful

**Example:** "The 'Submit' action in ERPNext makes a document permanent and triggers related workflows. Once submitted, documents can only be amended or cancelled, not edited directly."

# Quality Criteria

Only extract knowledge that meets ALL these criteria:
✅ **Specific to ERPNext**: Must be about ERPNext operations, not generic advice
✅ **Actionable**: Must contain concrete information users can act on
✅ **Reusable**: Must be applicable to future similar situations
✅ **Accurate**: Must be correct based on the conversation outcome
✅ **Complete**: Must contain enough detail to be useful standalone

Do NOT extract:
❌ Generic information obvious to any ERPNext user
❌ Incomplete or unsuccessful attempts
❌ User-specific data (names, specific IDs, etc.)
❌ Conversational filler or greetings

# Analyzing MCP Tool Usage

When analyzing conversations, **pay special attention to MCP tool calls** (marked as "→ MCP Tool Call:"):

**What to capture from tool usage:**
- **Tool sequences**: Order of tools called to accomplish a task
- **Tool parameters**: Which parameters were used and why
- **Efficient patterns**: Tool usage that was successful and efficient
- **Tool combinations**: Multiple tools used together effectively

**When to capture as best practice/shortcut:**
- Tool usage resulted in successful operation
- Pattern demonstrates efficiency or best approach
- Tool parameters show proper field usage
- Sequence can be generalized to similar scenarios

**Example MCP tool patterns to capture:**
- "Create Sales Order efficiently: Call `get_required_fields` first, then `create_document` with all mandatory fields"
- "Bulk operations: Use `list_documents` with filters, then iterate with `update_document`"
- "Workflow completion: `get_document` to verify state, then `apply_workflow` with action"

# Output Format

Return a JSON object with this structure:

{{
  "should_save": true/false,
  "entries": [
    {{
      "knowledge_type": "best_practice|shortcut|error_solution|general_knowledge",
      "title": "Clear, descriptive title (5-10 words)",
      "content": "Detailed explanation with context and steps. For best_practice/shortcut, include why this approach is recommended.",
      "summary": "One-sentence summary of the knowledge",
      "possible_queries": [
        "How do I [action]?",
        "What is the best way to [task]?",
        "How to [alternative phrasing]?",
        "[Keyword-based query variation]"
      ],
      "doctype_name": "Related DocType or null",
      "module": "ERPNext module (e.g., 'Selling', 'Stock', 'Accounts') or null",
      "category": "Category for processes (e.g., 'Sales & Delivery', 'Stock Management') or null",
      "priority": 70-90,

      // Only include for best_practice or shortcut:
      "steps": {{
        "1": {{
          "step_id": "unique_step_id",
          "title": "Step Title",
          "description": "What to do in this step",
          "action_type": "validation|create_document|update_document|submit_document|search|workflow",
          "target_doctype": "DocType name or null",
          "mcp_tool_name": "create_document|get_document|list_documents|update_document|delete_document|apply_workflow or null"
        }},
        "2": {{ ... }}
      }},
      "trigger_conditions": {{
        "doctype": "DocType that triggers this process",
        "status": "Document status if applicable"
      }},
      "prerequisites": {{
        "required_roles": ["List of required ERPNext roles"],
        "required_doctypes": ["List of DocTypes that must exist"]
      }}
    }}
  ]
}}

# Generating Possible Queries

For each knowledge entry, extract 3-5 natural language queries that users might ask to find this knowledge:

**Query Variation Guidelines:**
- Use different question formats: "How do I...", "What is...", "How to...", "Best way to..."
- Include both formal and informal variations
- Use synonyms and alternative terms for key concepts
- Consider different user skill levels (beginner to advanced)
- Include keyword-based queries (without question words)
- Match the language style users actually use in conversations

**Examples of Good Query Variations:**
- "How do I check credit limit before creating a sales order?"
- "What is the best practice for sales order credit validation?"
- "How to verify customer credit in ERPNext?"
- "Sales order credit limit check process"

# Process Structure Guidelines (for best_practice/shortcut)

When extracting best practices or shortcuts, structure them as executable process steps:

**Good Process Steps:**
- Each step is a discrete action
- Steps are ordered sequentially
- Each step has clear action_type
- Steps can be followed independently

**action_type options:**
- `validation`: Check or verify something
- `create_document`: Create a new DocType
- `update_document`: Modify an existing document
- `submit_document`: Submit a document
- `search`: Search or query data
- `workflow`: Workflow action (approve, reject, etc.)
- `calculation`: Calculate or compute values
- `notification`: Send notification or alert

# Examples

## Example 1: Best Practice
```json
{{
  "should_save": true,
  "entries": [
    {{
      "knowledge_type": "best_practice",
      "title": "Sales Order Creation with Credit Limit Check",
      "content": "When creating sales orders, always verify customer credit limit before confirming the order to prevent payment issues. This best practice ensures financial discipline and reduces risk of bad debt.",
      "summary": "Verify customer credit limit before creating sales orders",
      "possible_queries": [
        "How do I check credit limit before creating a sales order?",
        "What is the best practice for sales order credit validation?",
        "How to verify customer credit in ERPNext sales order?",
        "Sales order credit limit check process"
      ],
      "doctype_name": "Sales Order",
      "module": "Selling",
      "category": "Sales & Delivery",
      "priority": 85,
      "steps": {{
        "1": {{
          "step_id": "get_customer_details",
          "title": "Get Customer Details",
          "description": "Retrieve customer information to check credit limit",
          "action_type": "search",
          "target_doctype": "Customer",
          "mcp_tool_name": "get_document"
        }},
        "2": {{
          "step_id": "check_outstanding",
          "title": "List Outstanding Invoices",
          "description": "Check for overdue invoices that might affect credit",
          "action_type": "search",
          "target_doctype": "Sales Invoice",
          "mcp_tool_name": "list_documents"
        }},
        "3": {{
          "step_id": "get_required_fields",
          "title": "Get Sales Order Required Fields",
          "description": "Fetch mandatory fields for Sales Order creation",
          "action_type": "validation",
          "target_doctype": "Sales Order",
          "mcp_tool_name": "get_required_fields"
        }},
        "4": {{
          "step_id": "create_order",
          "title": "Create Sales Order",
          "description": "Create sales order with all required fields after credit verification",
          "action_type": "create_document",
          "target_doctype": "Sales Order",
          "mcp_tool_name": "create_document"
        }}
      }},
      "trigger_conditions": {{
        "doctype": "Sales Order",
        "status": "Draft"
      }},
      "prerequisites": {{
        "required_roles": ["Sales User"],
        "required_doctypes": ["Customer", "Sales Order"]
      }}
    }}
  ]
}}
```

## Example 2: Error Solution
```json
{{
  "should_save": true,
  "entries": [
    {{
      "knowledge_type": "error_solution",
      "title": "Fix 'Missing paid_from Account' in Payment Entry",
      "content": "Error: ValidationError when submitting Payment Entry - 'paid_from' account is mandatory. Solution: Always set the 'paid_from' account field before submission. For cash payments, use 'Cash - [Company]'. For bank payments, select the appropriate bank account.",
      "summary": "Payment Entry requires paid_from account to be set before submission",
      "possible_queries": [
        "How to fix missing paid_from account error?",
        "Payment Entry validation error paid_from",
        "What to do when payment entry will not submit?",
        "How to set paid_from account in ERPNext?"
      ],
      "doctype_name": "Payment Entry",
      "module": "Accounts",
      "category": null,
      "priority": 80
    }}
  ]
}}
```

# Conversation to Analyze

{conversation}

# Instructions

1. Read the entire conversation carefully
2. Identify any valuable ERPNext knowledge discussed
3. For each piece of knowledge, determine its type
4. Structure best practices and shortcuts as processes with clear steps
5. Return JSON following the exact format above
6. Set "should_save" to false if no valuable knowledge is found
"""
