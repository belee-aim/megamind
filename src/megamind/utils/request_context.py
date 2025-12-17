"""Request context for megamind.

Uses Python's contextvars to store request-scoped data like access tokens
and thread IDs that can be accessed by tools/middleware at runtime without
needing to rebuild graphs.
"""

from contextvars import ContextVar
from typing import Optional

# Context variable for storing the current request's access token
_access_token_var: ContextVar[Optional[str]] = ContextVar("access_token", default=None)

# Context variable for storing the current request's thread ID
_thread_id_var: ContextVar[Optional[str]] = ContextVar("thread_id", default=None)


def set_access_token(token: str) -> None:
    """Set the access token for the current request context."""
    _access_token_var.set(token)


def get_access_token() -> Optional[str]:
    """Get the access token from the current request context."""
    return _access_token_var.get()


def clear_access_token() -> None:
    """Clear the access token from the current request context."""
    _access_token_var.set(None)


def set_thread_id(thread_id: str) -> None:
    """Set the thread ID for the current request context."""
    _thread_id_var.set(thread_id)


def get_thread_id() -> Optional[str]:
    """Get the thread ID from the current request context."""
    return _thread_id_var.get()


def clear_thread_id() -> None:
    """Clear the thread ID from the current request context."""
    _thread_id_var.set(None)
