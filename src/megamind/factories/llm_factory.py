"""
LLM Factory for creating language model instances based on provider configuration.

Supports multiple providers: GEMINI, DEEPSEEK, CLAUDE, and KIMI
Uses Factory design pattern for flexible provider switching via environment variables.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional
from loguru import logger

from langchain_core.language_models import BaseChatModel
from langchain_core.embeddings import Embeddings


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def create_chat_model(
        self, model: str, api_key: str, **kwargs
    ) -> BaseChatModel:
        """Create a chat model instance."""
        pass

    @abstractmethod
    def create_embeddings(
        self, model: str, api_key: str, **kwargs
    ) -> Embeddings:
        """Create an embeddings model instance."""
        pass

    @abstractmethod
    def get_default_model(self) -> str:
        """Get the default model name for this provider."""
        pass

    @abstractmethod
    def get_default_embedding_model(self) -> str:
        """Get the default embedding model name for this provider."""
        pass


class GeminiProvider(LLMProvider):
    """Google Gemini provider implementation."""

    def create_chat_model(
        self, model: str, api_key: str, **kwargs
    ) -> BaseChatModel:
        from langchain_google_genai import ChatGoogleGenerativeAI

        logger.debug(f"Creating Gemini chat model: {model}")
        return ChatGoogleGenerativeAI(
            model=model, google_api_key=api_key, **kwargs
        )

    def create_embeddings(
        self, model: str, api_key: str, **kwargs
    ) -> Embeddings:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        logger.debug(f"Creating Gemini embeddings model: {model}")
        return GoogleGenerativeAIEmbeddings(
            model=model, google_api_key=api_key, **kwargs
        )

    def get_default_model(self) -> str:
        return "gemini-2.5-flash"

    def get_default_embedding_model(self) -> str:
        return "models/embedding-001"


class DeepSeekProvider(LLMProvider):
    """DeepSeek provider implementation (OpenAI-compatible)."""

    def create_chat_model(
        self, model: str, api_key: str, **kwargs
    ) -> BaseChatModel:
        from langchain_openai import ChatOpenAI

        logger.debug(f"Creating DeepSeek chat model: {model}")
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url="https://api.deepseek.com/v1",
            **kwargs,
        )

    def create_embeddings(
        self, model: str, api_key: str, **kwargs
    ) -> Embeddings:
        from langchain_openai import OpenAIEmbeddings

        logger.debug(f"Creating DeepSeek embeddings model: {model}")
        # DeepSeek doesn't have native embeddings, so we use their text-embedding model
        return OpenAIEmbeddings(
            model=model,
            api_key=api_key,
            base_url="https://api.deepseek.com/v1",
            **kwargs,
        )

    def get_default_model(self) -> str:
        return "deepseek-chat"

    def get_default_embedding_model(self) -> str:
        # DeepSeek doesn't have a dedicated embedding model yet
        # Fall back to using a small chat model for embeddings if needed
        return "deepseek-chat"


class ClaudeProvider(LLMProvider):
    """Anthropic Claude provider implementation."""

    def create_chat_model(
        self, model: str, api_key: str, **kwargs
    ) -> BaseChatModel:
        from langchain_anthropic import ChatAnthropic

        logger.debug(f"Creating Claude chat model: {model}")
        return ChatAnthropic(model=model, api_key=api_key, **kwargs)

    def create_embeddings(
        self, model: str, api_key: str, **kwargs
    ) -> Embeddings:
        # Claude doesn't provide embedding models
        # Fall back to using Voyage AI embeddings (Anthropic's recommended partner)
        # or raise an error to prompt user to use a different provider for embeddings
        logger.warning(
            "Claude does not provide embedding models. "
            "Please use GEMINI or DEEPSEEK for embeddings, "
            "or configure a separate embedding provider."
        )
        raise NotImplementedError(
            "Claude does not provide embedding models. "
            "Please set PROVIDER=GEMINI for embeddings or use a separate embedding service."
        )

    def get_default_model(self) -> str:
        return "claude-sonnet-4-5-20250929"

    def get_default_embedding_model(self) -> str:
        # Claude doesn't have embeddings
        raise NotImplementedError(
            "Claude does not provide embedding models. Use GEMINI or DEEPSEEK for embeddings."
        )


class KimiProvider(LLMProvider):
    """Moonshot KIMI provider implementation (OpenAI-compatible)."""

    def create_chat_model(
        self, model: str, api_key: str, **kwargs
    ) -> BaseChatModel:
        from langchain_openai import ChatOpenAI

        logger.debug(f"Creating KIMI chat model: {model}")
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url="https://api.moonshot.ai/v1",
            **kwargs,
        )

    def create_embeddings(
        self, model: str, api_key: str, **kwargs
    ) -> Embeddings:
        # KIMI doesn't provide embedding models
        logger.warning(
            "KIMI does not provide embedding models. "
            "Please use GEMINI or DEEPSEEK for embeddings, "
            "or configure a separate embedding provider."
        )
        raise NotImplementedError(
            "KIMI does not provide embedding models. "
            "Please set PROVIDER=GEMINI for embeddings or use a separate embedding service."
        )

    def get_default_model(self) -> str:
        return "moonshotai/Kimi-K2-Thinking"

    def get_default_embedding_model(self) -> str:
        # KIMI doesn't have embeddings
        raise NotImplementedError(
            "KIMI does not provide embedding models. Use GEMINI or DEEPSEEK for embeddings."
        )


class LLMFactory:
    """
    Factory class for creating LLM instances based on provider configuration.

    Supports GEMINI, DEEPSEEK, CLAUDE, and KIMI providers.
    """

    _providers = {
        "GEMINI": GeminiProvider(),
        "DEEPSEEK": DeepSeekProvider(),
        "CLAUDE": ClaudeProvider(),
        "KIMI": KimiProvider(),
    }

    @classmethod
    def create_chat_model(
        cls,
        provider: str,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        **kwargs,
    ) -> BaseChatModel:
        """
        Create a chat model instance based on the provider.

        Args:
            provider: Provider name (GEMINI, DEEPSEEK, or CLAUDE)
            model: Model name (optional, uses provider default if not specified)
            api_key: API key for the provider
            **kwargs: Additional arguments to pass to the model constructor

        Returns:
            BaseChatModel: A chat model instance

        Raises:
            ValueError: If provider is not supported
        """
        provider = provider.upper()

        if provider not in cls._providers:
            raise ValueError(
                f"Unsupported provider: {provider}. "
                f"Supported providers: {', '.join(cls._providers.keys())}"
            )

        provider_instance = cls._providers[provider]

        # Use default model if not specified
        if not model:
            model = provider_instance.get_default_model()
            logger.debug(f"Using default model for {provider}: {model}")

        if not api_key:
            raise ValueError(f"API key is required for provider: {provider}")

        logger.info(f"Creating chat model with provider={provider}, model={model}")
        return provider_instance.create_chat_model(model, api_key, **kwargs)

    @classmethod
    def create_embeddings(
        cls,
        provider: str,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        **kwargs,
    ) -> Embeddings:
        """
        Create an embeddings model instance based on the provider.

        Args:
            provider: Provider name (GEMINI, DEEPSEEK, or CLAUDE)
            model: Embedding model name (optional, uses provider default if not specified)
            api_key: API key for the provider
            **kwargs: Additional arguments to pass to the embeddings constructor

        Returns:
            Embeddings: An embeddings model instance

        Raises:
            ValueError: If provider is not supported
            NotImplementedError: If provider doesn't support embeddings
        """
        provider = provider.upper()

        if provider not in cls._providers:
            raise ValueError(
                f"Unsupported provider: {provider}. "
                f"Supported providers: {', '.join(cls._providers.keys())}"
            )

        provider_instance = cls._providers[provider]

        # Use default embedding model if not specified
        if not model:
            model = provider_instance.get_default_embedding_model()
            logger.debug(f"Using default embedding model for {provider}: {model}")

        if not api_key:
            raise ValueError(f"API key is required for provider: {provider}")

        logger.info(
            f"Creating embeddings model with provider={provider}, model={model}"
        )
        return provider_instance.create_embeddings(model, api_key, **kwargs)

    @classmethod
    def get_available_providers(cls) -> list[str]:
        """Get a list of available provider names."""
        return list(cls._providers.keys())

    @classmethod
    def get_provider_default_model(cls, provider: str) -> str:
        """Get the default model name for a provider."""
        provider = provider.upper()
        if provider not in cls._providers:
            raise ValueError(f"Unsupported provider: {provider}")
        return cls._providers[provider].get_default_model()

    @classmethod
    def get_provider_default_embedding_model(cls, provider: str) -> str:
        """Get the default embedding model name for a provider."""
        provider = provider.upper()
        if provider not in cls._providers:
            raise ValueError(f"Unsupported provider: {provider}")
        return cls._providers[provider].get_default_embedding_model()
