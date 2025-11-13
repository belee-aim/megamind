"""
Prompt for Corrective RAG (CRAG) pattern.

This prompt is used to generate improved knowledge search queries when
ERPNext operations fail, helping the system recover from errors.
"""

corrective_query_generation_instructions = """You are an expert at analyzing ERPNext errors and generating targeted knowledge search queries.

# Context
The user attempted an ERPNext operation that failed with an error.

**Recent Conversation:**
{context_str}

**Failed Tool:** {tool_name}
**DocType:** {doctype}
**Error Message:** {error_description}

# Task
Generate a precise knowledge search query that will retrieve information to fix this error.

Focus on:
1. Required fields that might be missing
2. Validation rules that were violated
3. Correct workflow sequences
4. Field formats and data types
5. Common pitfalls for this operation

# Output Format
Return ONLY the search query text, nothing else. Make it specific and actionable.

# Examples
- "Sales Order required fields and validation rules for creation"
- "Payment Entry mandatory fields and workflow sequence"
- "Stock Entry item table required child fields and formats"

# Your Query:"""
