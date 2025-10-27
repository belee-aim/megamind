import os
from pydantic import BaseModel, Field
from typing import Any, Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.language_models import BaseChatModel
from langchain_core.embeddings import Embeddings

from megamind.factories import LLMFactory
from megamind.utils.config import settings


class Configuration(BaseModel):
    """The configuration for the agent."""

    embedding_model: str = Field(
        default="models/embedding-001",
        description="The name of the embedding model to use for the agent.",
    )

    query_generator_model: str = Field(
        default="gemini-2.5-pro",
        description="The name of the language model to use for the agent's query generation.",
    )

    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
    ) -> "Configuration":
        """Create a Configuration instance from a RunnableConfig."""
        configurable = (
            config["configurable"] if config and "configurable" in config else {}
        )

        # Get raw values from environment or config
        raw_values: dict[str, Any] = {
            name: os.environ.get(name.upper(), configurable.get(name))
            for name in cls.model_fields.keys()
        }

        # Filter out None values
        values = {k: v for k, v in raw_values.items() if v is not None}

        return cls(**values)

    def get_chat_model(self, **kwargs) -> BaseChatModel:
        """
        Create a chat model instance using the configured provider.

        Args:
            **kwargs: Additional arguments to pass to the model constructor

        Returns:
            BaseChatModel: A chat model instance
        """
        # Determine API key (support both new and legacy config)
        api_key = settings.api_key or settings.google_api_key

        # Use configured model or settings model
        model = settings.model or self.query_generator_model

        return LLMFactory.create_chat_model(
            provider=settings.provider,
            model=model,
            api_key=api_key,
            **kwargs,
        )

    def get_embeddings(self, **kwargs) -> Embeddings:
        """
        Create an embeddings model instance using the configured provider.

        Args:
            **kwargs: Additional arguments to pass to the embeddings constructor

        Returns:
            Embeddings: An embeddings model instance
        """
        # Determine API key (support both new and legacy config)
        api_key = settings.api_key or settings.google_api_key

        # Use configured embedding model or settings embedding model
        embedding_model = settings.embedding_model or self.embedding_model

        return LLMFactory.create_embeddings(
            provider=settings.provider,
            model=embedding_model,
            api_key=api_key,
            **kwargs,
        )
