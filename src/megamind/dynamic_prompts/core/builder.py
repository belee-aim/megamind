import re
from typing import Dict, Any
from .models import PromptVariant, SystemContext, ComponentFunction


class PromptBuilder:
    def __init__(
        self,
        variant: PromptVariant,
        context: SystemContext,
        components: Dict[str, ComponentFunction],
    ):
        self.variant = variant
        self.context = context
        self.components = components

    async def build(self) -> str:
        component_sections = await self._build_components()
        placeholder_values = self._prepare_placeholders(component_sections)

        # Simple string formatting as the template engine
        prompt = self.variant.base_template.format(**placeholder_values)
        return self._post_process(prompt)

    async def _build_components(self) -> Dict[str, str]:
        sections = {}
        for component_id in self.variant.component_order:
            component_fn = self.components.get(component_id)
            if component_fn:
                result = await component_fn(self.variant, self.context)
                if result and result.strip():
                    sections[component_id] = result
        return sections

    def _prepare_placeholders(
        self, component_sections: Dict[str, str]
    ) -> Dict[str, Any]:
        placeholders = {}
        placeholders.update(self.variant.placeholders)
        placeholders.update(self.context.runtime_placeholders)
        placeholders.update(component_sections)

        # Ensure all keys from component_order are present to avoid KeyError
        for key in self.variant.component_order:
            placeholders.setdefault(key, "")

        return placeholders

    def _post_process(self, prompt: str) -> str:
        # Replicate the post-processing logic from the TypeScript version
        processed_prompt = re.sub(r"\n\s*\n\s*\n", "\n\n", prompt).strip()
        return processed_prompt
