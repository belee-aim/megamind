"""
Prompts package for Megamind.

This package organizes all prompts into separate modules by functionality.
All prompts are re-exported here for backward compatibility with existing imports.

Usage:
    from megamind import prompts
    prompts.wiki_agent_instructions
    prompts.build_system_prompt(company="Example", current_datetime="2025-01-01")
"""

# Import from megamind module (base system prompt)
from megamind.prompts.megamind import (
    BASE_SYSTEM_PROMPT,
    build_system_prompt,
)

# Import from minion module (wiki and document agents)
from megamind.prompts.minion import (
    wiki_agent_instructions,
    document_agent_instructions,
)

# Import from role_generation module
from megamind.prompts.role_generation import (
    role_generation_agent_instructions,
    permission_description_agent_instructions,
)

# Import from document_extraction module
from megamind.prompts.document_extraction import (
    fact_extraction_agent_instructions,
    value_inference_agent_instructions,
)

# Import from corrective_rag module
from megamind.prompts.corrective_rag import (
    corrective_query_generation_instructions,
)

# Import from knowledge_capture module
from megamind.prompts.knowledge_capture import (
    knowledge_extraction_agent_instructions,
)

# Export all for convenient access
__all__ = [
    # Megamind (base system prompt)
    "BASE_SYSTEM_PROMPT",
    "build_system_prompt",
    # Minion agents
    "wiki_agent_instructions",
    "document_agent_instructions",
    # Role generation
    "role_generation_agent_instructions",
    "permission_description_agent_instructions",
    # Document extraction
    "fact_extraction_agent_instructions",
    "value_inference_agent_instructions",
    # Corrective RAG
    "corrective_query_generation_instructions",
    # Knowledge capture
    "knowledge_extraction_agent_instructions",
]
