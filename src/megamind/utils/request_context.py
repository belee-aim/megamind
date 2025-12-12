"""Request context for megamind.

Uses Python's contextvars to store request-scoped data like access tokens
that can be accessed by tools at runtime without needing to rebuild graphs.
"""

from contextvars import ContextVar
from typing import Optional

# Context variable for storing the current request's access token
_access_token_var: ContextVar[Optional[str]] = ContextVar("access_token", default=None)


def set_access_token(token: str) -> None:
    """Set the access token for the current request context."""
    _access_token_var.set(token)


def get_access_token() -> Optional[str]:
    """Get the access token from the current request context."""
    return _access_token_var.get()


def clear_access_token() -> None:
    """Clear the access token from the current request context."""
    _access_token_var.set(None)
