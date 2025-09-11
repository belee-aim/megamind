from pydantic import BaseModel, Field
from typing import List, Dict, Any, Callable, Awaitable


class ProviderInfo(BaseModel):
    # Simplified for this example
    model_id: str
    family: str = Field(
        default="generic",
        description="The prompt structure name in dynamic_prompts/variants.",
    )


class SystemContext(BaseModel):
    provider_info: ProviderInfo
    cwd: str
    # Add other context-dependent fields as needed
    # e.g., user_instructions: str | None = None
    runtime_placeholders: Dict[str, Any] = Field(default_factory=dict)


class PromptVariant(BaseModel):
    id: str
    family: str
    version: int = 1
    base_template: str
    component_order: List[str]
    placeholders: Dict[str, Any] = Field(default_factory=dict)
    # We can add tools, tags, etc. later


# Type hint for a component function
ComponentFunction = Callable[["PromptVariant", "SystemContext"], Awaitable[str | None]]
