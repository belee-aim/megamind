from megamind.dynamic_prompts.core.models import PromptVariant, SystemContext

EXECUTION_FLOW_TEXT = """
# Transfer Execution Flow

## Default Warehouse Behavior & Auto-Field Population
**COMPLETE AUTOMATION - Only ask for item code and quantity:**
- **Source Warehouse**: Automatically select main central warehouse
- **Target Warehouse**: Automatically select user's branch warehouse
- **Only 2 pieces of information needed**: Item code/name + Quantity
- **ALL other fields are auto-populated**

## Business Logic Rules:
1. **Never ask for warehouse information** - it is auto-determined.
2. **Never ask for the company** - it is taken from the user's session.
3. **Never ask for stock entry type** - it is always "Material Transfer".
4. **Only ask for**: The item identifier (code, name, etc.) and the quantity.

## Finalizing Transfer
After all desired items are added:
- Ask: **"Таны барааны захиалга дууссан бол илгээх үү?"**
- If user agrees, the system will submit the Stock Entry.
"""


async def get_execution_flow_section(
    variant: PromptVariant, context: SystemContext
) -> str:
    """
    Returns the execution flow instructions for the stock movement agent.
    """
    return EXECUTION_FLOW_TEXT
