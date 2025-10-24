# Dynamic Prompt System

A flexible, modular system for building AI agent prompts from reusable components. This system powers the Megamind LangGraph workflows by generating context-aware, role-specific system prompts.

## Overview

The dynamic prompt system allows you to:
- **Compose prompts from reusable components** - Build prompts by combining modular sections
- **Create specialized variants** - Define agent-specific prompt structures via YAML
- **Inject runtime context** - Pass dynamic values (company name, permissions, etc.) at runtime
- **Maintain consistency** - Share common components across multiple agent types
- **Version and test** - Track prompt versions and test variants independently

## Architecture

```
dynamic_prompts/
├── core/
│   ├── builder.py         # PromptBuilder - assembles components into final prompt
│   ├── registry.py        # PromptRegistry - singleton that loads/manages variants
│   └── models.py          # Pydantic models for type safety
├── components/
│   ├── agent_role.py      # Generic agent role description
│   ├── constraints.py     # Safety protocols and constraints
│   ├── tool_usage.py      # Tool usage instructions
│   └── ...                # Other reusable prompt sections
├── variants/
│   ├── generic.yaml       # General-purpose agent configuration
│   ├── stock_movement.yaml
│   └── accounting_finance.yaml
└── docs/                  # Detailed guides and best practices
```

## How It Works

### 1. Component Registration

Components are Python functions that return prompt text:

```python
# components/agent_role.py
async def get_agent_role_section(variant: PromptVariant, context: SystemContext) -> str:
    return "You are Aimlink Agent, a professional AI assistant..."
```

Components are registered in `components/__init__.py`:

```python
component_registry: Dict[str, ComponentFunction] = {
    "AGENT_ROLE": agent_role.get_agent_role_section,
    "CONSTRAINTS": constraints.get_constraints_section,
    # ...
}
```

### 2. Variant Definition

Variants are YAML files that define prompt structure:

```yaml
id: "generic"
family: "generic"
version: 1
base_template: |
  ## 1. Core Persona
  {AGENT_ROLE}

  ## 2. Primary Directives
  {PRIMARY_DIRECTIVES}

  ## 3. Communication Rules
  {COMMUNICATION_RULES}

component_order:
  - "AGENT_ROLE"
  - "PRIMARY_DIRECTIVES"
  - "COMMUNICATION_RULES"

placeholders: {}
```

### 3. Runtime Prompt Generation

At request time, the system:

1. **Loads the variant** - Based on the `prompt_family` in the request
2. **Builds components** - Calls each component function with runtime context
3. **Injects values** - Substitutes placeholders with actual values
4. **Assembles prompt** - Combines everything into final system prompt

```python
from megamind.dynamic_prompts.core.registry import prompt_registry
from megamind.dynamic_prompts.core.models import SystemContext, ProviderInfo

# Create context with runtime values
context = SystemContext(
    provider_info=ProviderInfo(family="accounting_finance"),
    runtime_placeholders={
        "company": "ACME Corp"
    }
)

# Generate prompt
system_prompt = await prompt_registry.get(context)
```

## Key Concepts

### Components

**Components** are reusable prompt sections. They can:
- Be shared across multiple variants (e.g., `CONSTRAINTS`, `TOOL_USAGE`)
- Be variant-specific (e.g., `ACCOUNTING_FINANCE_AGENT_ROLE`)
- Access runtime context to inject dynamic values
- Return `None` or empty string to be excluded from final prompt

### Variants

**Variants** define agent types. Each variant:
- Specifies which components to include
- Defines the order and structure of the prompt
- Can have variant-specific components
- Is identified by a `family` name used in routing

### Context

**SystemContext** carries runtime information:
- `provider_info.family` - Which variant to use
- `runtime_placeholders` - Dynamic values like company name, user permissions

### Component Order

The `component_order` in YAML controls:
- Which components are included
- The sequence they appear in the prompt
- Any component not in the order is excluded

## Usage

### At Application Startup

```python
# src/megamind/main.py
from megamind.dynamic_prompts.core.registry import prompt_registry

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load all variants and components
    await prompt_registry.load()
    yield
```

### In Endpoint Handlers

```python
# When creating a new thread, build system prompt
if thread_state is None:
    context = SystemContext(
        provider_info=ProviderInfo(family=prompt_family),
        runtime_placeholders={
            "company": settings.company_name
        }
    )
    system_prompt = await prompt_registry.get(context)
    messages.append(SystemMessage(content=system_prompt))
```

### Testing Variants

```bash
# Test a specific variant
python tests/test_prompt_builder.py --variant accounting_finance

# Test all variants
python tests/test_prompt_builder.py
```

## Available Variants

| Variant ID | Family | Purpose | Endpoints |
|------------|--------|---------|-----------|
| `generic` | generic | General-purpose assistant | `/api/v1/stream/{thread}` |
| `stock_movement` | stock_movement | Inventory management | `/api/v1/stock-movement/stream/{thread}` |
| `accounting_finance` | accounting_finance | Financial operations | `/api/v1/accounting-finance/stream/{thread}` |

## Common Components

| Component ID | Purpose | Used By |
|--------------|---------|---------|
| `AGENT_ROLE` | Generic agent identity | generic |
| `PRIMARY_DIRECTIVES` | Core responsibilities | generic, accounting_finance |
| `COMMUNICATION_RULES` | Language, tone, interaction style | All variants |
| `TOOL_USAGE` | How to use tools effectively | All variants |
| `CONSTRAINTS` | Safety protocols, permissions | All variants |
| `CLIENT_FUNCTIONS` | Client-side XML rendering | All variants |
| `EXAMPLES` | Few-shot examples | All variants |
| `INCORRECT_USAGE` | Anti-patterns to avoid | All variants |

## Best Practices

1. **Keep components focused** - Each component should have a single responsibility
2. **Use descriptive IDs** - Component IDs should be UPPER_SNAKE_CASE and descriptive
3. **Test after changes** - Run the test script after modifying components or variants
4. **Version your variants** - Increment `version` when making breaking changes
5. **Document complex logic** - Add docstrings explaining non-obvious component behavior
6. **Use placeholders for dynamic data** - Never hardcode values that change per request
7. **Share components when possible** - Reuse existing components before creating new ones

## Guides

- **[Component Guide](docs/COMPONENT_GUIDE.md)** - How to create and modify components
- **[Variant Guide](docs/VARIANT_GUIDE.md)** - How to create new agent variants
- **[Best Practices](docs/BEST_PRACTICES.md)** - Prompt engineering tips and testing strategies

## Troubleshooting

### "No suitable prompt variant found"

**Cause:** The requested `family` doesn't have a matching variant YAML file.

**Solution:** Check that:
1. The YAML file exists in `variants/`
2. The `family` field in YAML matches the requested family
3. The registry loaded successfully at startup

### Component not appearing in prompt

**Cause:** Component ID not in `component_order` or function returns empty string.

**Solution:**
1. Verify component ID is in the variant's `component_order` list
2. Check the component function returns non-empty content
3. Ensure component is registered in `components/__init__.py`

### Placeholder not substituting

**Cause:** Placeholder name mismatch or not passed in runtime context.

**Solution:**
1. Check placeholder names match exactly (case-sensitive)
2. Verify value is in `context.runtime_placeholders`
3. Use `{placeholder_name}` syntax in component text

## Performance Considerations

- **Registry is a singleton** - Variants and components load once at startup
- **Components are async** - Design for potential async operations (DB lookups, etc.)
- **Caching** - The registry caches loaded variants; no per-request parsing
- **Prompt size** - Monitor token counts; very long prompts impact latency and cost

## Contributing

When adding new components or variants:

1. Follow existing naming conventions
2. Add comprehensive docstrings
3. Test with `test_prompt_builder.py`
4. Update this README if adding new variants
5. Document any new patterns in the guides

## Related Files

- **Main application:** `src/megamind/main.py` - Where prompts are generated and used
- **Static prompts:** `src/megamind/prompts.py` - Legacy static prompts for non-megamind graphs
- **Graph definitions:** `src/megamind/graph/workflows/` - LangGraph workflows using these prompts
- **Test script:** `tests/test_prompt_builder.py` - Variant testing utility
