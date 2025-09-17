import sys
from pathlib import Path

# Add the 'src' directory to the Python path to resolve module imports
src_path = Path(__file__).resolve().parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import asyncio
import argparse
from megamind.dynamic_prompts.core.models import ProviderInfo, SystemContext
from megamind.dynamic_prompts.core.registry import prompt_registry


async def main(variant_name: str):
    """
    Initializes and runs the PromptBuilder to generate and display a prompt.
    """
    print(f"--- Building prompt for variant: '{variant_name}' ---")

    try:
        # Load all prompt variants and their components
        await prompt_registry.load()

        # Create a context object with runtime information
        context = SystemContext(
            provider_info=ProviderInfo(family=variant_name),
            runtime_placeholders={
                "team_ids": ["Team A", "Team B"],
                "user_query": "How do I create a new sales order?",
            },
        )

        # Get the fully assembled and formatted prompt
        system_prompt = await prompt_registry.get(context)

        print("\n--- Generated Prompt ---")
        print(system_prompt)
        print("\n--- End of Prompt ---")

    except FileNotFoundError:
        print(f"Error: The variant '{variant_name}.yaml' was not found.")
        print(
            "Please ensure the variant file exists in 'src/megamind/dynamic_prompts/variants/'."
        )
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test the PromptBuilder.")
    parser.add_argument(
        "--variant",
        type=str,
        default="generic",
        help="The name of the prompt variant to test.",
    )
    args = parser.parse_args()
    asyncio.run(main(args.variant))
