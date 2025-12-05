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

    fast_model: str = Field(
        default="gemini-2.5-flash",
        description="The name of the language model to use for fast but inaccurate agent.",
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

    def get_chat_model(
        self, custom_model=None, as_string=False, **kwargs
    ) -> BaseChatModel | str:
        """
        Create a chat model instance or return model string.

        Args:
            custom_model: Custom model name to use instead of settings
            as_string: If True, return model string (provider:model) instead of instance
            **kwargs: Additional arguments to pass to the model constructor

        Returns:
            BaseChatModel: A chat model instance (default)
            str: Model string in format "provider:model" if as_string=True
        """
        # Determine API key (support both new and legacy config)
        api_key = settings.api_key or settings.google_api_key

        # Use configured model or settings model
        if custom_model:
            model = custom_model
        else:
            model = settings.model or self.query_generator_model

        # Return string format for Deep Agents
        if as_string:
            return self.get_model_string(model)

        return LLMFactory.create_chat_model(
            provider=settings.provider,
            model=model,
            api_key=api_key,
            **kwargs,
        )

    def get_model_string(self, custom_model: str = None) -> str:
        """
        Get model string in Deep Agents format (provider:model_name).

        Args:
            custom_model: Custom model name, defaults to settings.model

        Returns:
            str: Model string like "google:gemini-2.5-flash" or "anthropic:claude-sonnet-4-20250514"
        """
        model = custom_model or settings.model or self.query_generator_model

        # Map provider names to Deep Agents format
        provider_map = {
            "GEMINI": "google",
            "CLAUDE": "anthropic",
            "OPENAI": "openai",
        }
        provider = provider_map.get(settings.provider.upper())

        if provider:
            return f"{provider}:{model}"
        else:
            # For unsupported providers (KIMI, DEEPSEEK), return None
            # Caller should use get_chat_model() instead
            return None

    def get_model_for_deep_agent(self, custom_model: str = None):
        """
        Get model for Deep Agents - either string or LangChain model instance.

        Deep Agents supports: google, anthropic, openai as string format.
        For other providers (KIMI, DEEPSEEK), returns a LangChain model instance.

        Args:
            custom_model: Custom model name, defaults to settings.model

        Returns:
            str: Model string for supported providers (e.g., "google:gemini-2.5-flash")
            BaseChatModel: LangChain model instance for unsupported providers
        """
        model_string = self.get_model_string(custom_model)

        if model_string:
            return model_string
        else:
            # Return LangChain model instance for unsupported providers
            return self.get_chat_model(custom_model)

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
