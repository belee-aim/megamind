from typing import Dict
from . import (
    agent_role,
    primary_directives,
    communication_rules,
    tool_usage,
    constraints,
    client_functions,
    examples,
    incorrect_usage,
    stock_movement_agent_role,
    stock_movement_primary_function,
    stock_movement_execution_flow,
)
from ..core.models import ComponentFunction

# Maps component ID to the async function
component_registry: Dict[str, ComponentFunction] = {
    # Default components
    "AGENT_ROLE": agent_role.get_agent_role_section,
    "PRIMARY_DIRECTIVES": primary_directives.get_primary_directives_section,
    "COMMUNICATION_RULES": communication_rules.get_communication_rules_section,
    "TOOL_USAGE": tool_usage.get_tool_usage_section,
    "CONSTRAINTS": constraints.get_constraints_section,
    "CLIENT_FUNCTIONS": client_functions.get_client_functions_section,
    "EXAMPLES": examples.get_examples_section,
    "INCORRECT_USAGE": incorrect_usage.get_incorrect_usage_section,
    # Stock movement components
    "STOCK_MOVEMENT_AGENT_ROLE": stock_movement_agent_role.get_agent_role_section,
    "STOCK_MOVEMENT_PRIMARY_FUNCTION": stock_movement_primary_function.get_primary_function_section,
    "STOCK_MOVEMENT_EXECUTION_FLOW": stock_movement_execution_flow.get_execution_flow_section,
}
