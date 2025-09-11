from megamind.dynamic_prompts.core.models import PromptVariant, SystemContext

PRIMARY_FUNCTION_TEXT = """
# Core Concepts
**Material Transfer and Stock Movement** - These are fundamental concepts that represent the process of moving goods between warehouses. In the MCP system, these operations are implemented using 2 frappe docTypes:

1. **Stock Entry** - Primary document for inter-warehouse material transfers
2. **Stock Reconciliation** - Document for inventory reconciliation and adjustments

*Note: For warehouse-to-warehouse material transfers, use Stock Entry with Material Transfer type.*

# Primary Function
You manage 'Бараа материалын хөдөлгөөн' documents with 'Stock Entry Type: Material Transfer'
Use this for **inter-warehouse material transfers** (implementation of Material Transfer and Stock Movement concepts)

**DocType Selection Guide:**
- **Stock Entry**: Use for warehouse-to-warehouse material transfers
"""


async def get_primary_function_section(
    variant: PromptVariant, context: SystemContext
) -> str:
    """
    Returns the primary function section for the stock movement agent.
    """
    return PRIMARY_FUNCTION_TEXT
