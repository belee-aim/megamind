import yaml
from pathlib import Path
from typing import Dict
from .models import PromptVariant, ComponentFunction, SystemContext
from .builder import PromptBuilder
from ..components import component_registry


class PromptRegistry:
    _instance = None
    variants: Dict[str, PromptVariant]
    components: Dict[str, ComponentFunction]
    loaded: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PromptRegistry, cls).__new__(cls)
        return cls._instance

    async def load(self):
        if self.loaded:
            return
        self._load_variants()
        self._load_components()
        self.loaded = True
        print(
            f"Registry loaded with {len(self.variants)} variants and {len(self.components)} components."
        )

    def _load_variants(self):
        self.variants = {}
        variants_path = Path(__file__).parent.parent / "variants"
        for file_path in variants_path.glob("*.yaml"):
            with open(file_path, "r") as f:
                config_data = yaml.safe_load(f)
                variant = PromptVariant(**config_data)
                self.variants[variant.id] = variant

    def _load_components(self):
        self.components = component_registry

    async def get(self, context: SystemContext) -> str:
        await self.load()
        variant = self.variants.get(context.provider_info.family) or self.variants.get(
            "generic"
        )
        if not variant:
            raise ValueError(
                "No suitable prompt variant found and no generic fallback is available."
            )

        builder = PromptBuilder(variant, context, self.components)
        return await builder.build()


# Instantiate the singleton
prompt_registry = PromptRegistry()
