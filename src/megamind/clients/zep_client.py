"""
Zep Cloud client for user and thread management.
Provides enhanced memory capabilities alongside LangGraph checkpointing.
"""

from typing import Optional, List
from loguru import logger
from zep_cloud.client import AsyncZep
from zep_cloud.types import Message

from megamind.utils.config import settings


class ZepClient:
    """
    Client for interacting with Zep Cloud for user and thread management.

    Zep provides:
    - User fact extraction and persistence
    - Cross-session context retrieval
    - Semantic memory search
    - User profiling and personalization
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Zep client.

        Args:
            api_key: Optional API key override (defaults to settings.zep_api_key)
        """
        self.api_key = api_key or settings.zep_api_key

        if not self.api_key:
            logger.warning("Zep API key not configured. Memory features will be disabled.")
            self.client = None
        else:
            try:
                self.client = AsyncZep(api_key=self.api_key)
                logger.debug("Zep client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Zep client: {e}")
                self.client = None

    def is_available(self) -> bool:
        """Check if Zep client is available and configured."""
        return self.client is not None

    # ============= USER MANAGEMENT =============

    async def get_or_create_user(
        self,
        user_id: str,
        email: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[dict]:
        """
        Get existing user or create if doesn't exist.
        Auto-creates Zep users based on ERPNext user information.

        Args:
            user_id: Unique user identifier (use ERPNext email or user ID)
            email: User's email address
            first_name: User's first name
            last_name: User's last name
            metadata: Additional user metadata

        Returns:
            User dict if successful, None otherwise
        """
        if not self.is_available():
            logger.debug("Zep client not available, skipping user creation")
            return None

        try:
            # Try to get existing user
            try:
                user = await self.client.user.get(user_id=user_id)
                logger.debug(f"Retrieved existing Zep user: {user_id}")
                return user.model_dump() if hasattr(user, 'model_dump') else dict(user)
            except Exception:
                # User doesn't exist, create new one
                logger.info(f"Creating new Zep user: {user_id}")

                user = await self.client.user.add(
                    user_id=user_id,
                    email=email,
                    first_name=first_name or "",
                    last_name=last_name or "",
                    metadata=metadata or {},
                )

                logger.info(f"Successfully created Zep user: {user_id}")
                return user.model_dump() if hasattr(user, 'model_dump') else dict(user)

        except Exception as e:
            logger.error(f"Error creating/retrieving Zep user {user_id}: {e}")
            return None

    async def get_user(self, user_id: str) -> Optional[dict]:
        """Retrieve user by ID."""
        if not self.is_available():
            return None

        try:
            user = await self.client.user.get(user_id=user_id)
            logger.debug(f"Retrieved Zep user: {user_id}")
            return user.model_dump() if hasattr(user, 'model_dump') else dict(user)
        except Exception as e:
            logger.error(f"Error retrieving Zep user {user_id}: {e}")
            return None

    async def update_user(
        self,
        user_id: str,
        email: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[dict]:
        """Update user information."""
        if not self.is_available():
            return None

        try:
            user = await self.client.user.update(
                user_id=user_id,
                email=email,
                first_name=first_name,
                last_name=last_name,
                metadata=metadata,
            )
            logger.info(f"Updated Zep user: {user_id}")
            return user.model_dump() if hasattr(user, 'model_dump') else dict(user)
        except Exception as e:
            logger.error(f"Error updating Zep user {user_id}: {e}")
            return None

    async def delete_user(self, user_id: str) -> bool:
        """Delete user by ID."""
        if not self.is_available():
            return False

        try:
            await self.client.user.delete(user_id=user_id)
            logger.info(f"Deleted Zep user: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting Zep user {user_id}: {e}")
            return False

    async def list_users(self, limit: int = 100, page_number: int = 1) -> List[dict]:
        """List all users with pagination."""
        if not self.is_available():
            return []

        try:
            response = await self.client.user.list(page_size=limit, page_number=page_number)
            users = response.users if hasattr(response, 'users') else []
            serialized = [u.model_dump() if hasattr(u, 'model_dump') else dict(u) for u in users]
            logger.debug(f"Retrieved {len(serialized)} Zep users")
            return serialized
        except Exception as e:
            logger.error(f"Error listing Zep users: {e}")
            return []

    # ============= THREAD MANAGEMENT =============

    async def get_or_create_thread(
        self,
        thread_id: str,
        user_id: str,
        metadata: Optional[dict] = None,
    ) -> Optional[dict]:
        """
        Get existing thread or create if doesn't exist.

        Args:
            thread_id: Unique thread identifier (use same ID as LangGraph thread)
            user_id: User ID that owns this thread
            metadata: Additional thread metadata

        Returns:
            Thread dict if successful, None otherwise
        """
        if not self.is_available():
            return None

        try:
            # Try to get existing thread
            try:
                thread = await self.client.memory.get_session(session_id=thread_id)
                logger.debug(f"Retrieved existing Zep thread: {thread_id}")
                return thread.model_dump() if hasattr(thread, 'model_dump') else dict(thread)
            except Exception:
                # Thread doesn't exist, create new one
                logger.info(f"Creating new Zep thread: {thread_id} for user {user_id}")

                thread = await self.client.memory.add_session(
                    session_id=thread_id,
                    user_id=user_id,
                    metadata=metadata or {},
                )

                logger.info(f"Successfully created Zep thread: {thread_id}")
                return thread.model_dump() if hasattr(thread, 'model_dump') else dict(thread)

        except Exception as e:
            logger.error(f"Error creating/retrieving Zep thread {thread_id}: {e}")
            return None

    async def get_thread(self, thread_id: str) -> Optional[dict]:
        """Retrieve thread by ID."""
        if not self.is_available():
            return None

        try:
            thread = await self.client.memory.get_session(session_id=thread_id)
            logger.debug(f"Retrieved Zep thread: {thread_id}")
            return thread.model_dump() if hasattr(thread, 'model_dump') else dict(thread)
        except Exception as e:
            logger.error(f"Error retrieving Zep thread {thread_id}: {e}")
            return None

    async def update_thread(
        self,
        thread_id: str,
        metadata: Optional[dict] = None,
    ) -> Optional[dict]:
        """Update thread metadata."""
        if not self.is_available():
            return None

        try:
            thread = await self.client.memory.update_session(
                session_id=thread_id,
                metadata=metadata,
            )
            logger.info(f"Updated Zep thread: {thread_id}")
            return thread.model_dump() if hasattr(thread, 'model_dump') else dict(thread)
        except Exception as e:
            logger.error(f"Error updating Zep thread {thread_id}: {e}")
            return None

    async def delete_thread(self, thread_id: str) -> bool:
        """Delete thread by ID."""
        if not self.is_available():
            return False

        try:
            await self.client.memory.delete_session(session_id=thread_id)
            logger.info(f"Deleted Zep thread: {thread_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting Zep thread {thread_id}: {e}")
            return False

    async def list_threads(self, user_id: Optional[str] = None, limit: int = 100, page_number: int = 1) -> List[dict]:
        """List threads, optionally filtered by user."""
        if not self.is_available():
            return []

        try:
            if user_id:
                response = await self.client.user.get_sessions(user_id=user_id, page_size=limit, page_number=page_number)
            else:
                response = await self.client.memory.list_sessions(page_size=limit, page_number=page_number)

            threads = response.sessions if hasattr(response, 'sessions') else []
            serialized = [t.model_dump() if hasattr(t, 'model_dump') else dict(t) for t in threads]
            logger.debug(f"Retrieved {len(serialized)} Zep threads")
            return serialized
        except Exception as e:
            logger.error(f"Error listing Zep threads: {e}")
            return []

    # ============= MESSAGE MANAGEMENT =============

    async def add_messages(
        self,
        thread_id: str,
        messages: List[dict],
    ) -> bool:
        """
        Add messages to a thread for memory building.

        Args:
            thread_id: Thread ID to add messages to
            messages: List of message dicts with keys: role, content, name (optional)

        Returns:
            True if successful, False otherwise
        """
        if not self.is_available():
            return False

        try:
            # Convert to Zep Message format
            zep_messages = [
                Message(
                    role_type=msg.get("role", "user"),
                    content=msg.get("content", ""),
                    role=msg.get("name"),
                )
                for msg in messages
            ]

            await self.client.memory.add(
                session_id=thread_id,
                messages=zep_messages,
            )

            logger.debug(f"Added {len(messages)} messages to Zep thread {thread_id}")
            return True

        except Exception as e:
            logger.error(f"Error adding messages to Zep thread {thread_id}: {e}")
            return False

    async def get_messages(
        self,
        thread_id: str,
        limit: int = 50,
    ) -> List[dict]:
        """Retrieve messages from a thread."""
        if not self.is_available():
            return []

        try:
            memory = await self.client.memory.get(session_id=thread_id, lastn=limit)
            messages = memory.messages if hasattr(memory, 'messages') else []
            serialized = [m.model_dump() if hasattr(m, 'model_dump') else dict(m) for m in messages]
            logger.debug(f"Retrieved {len(serialized)} messages from Zep thread {thread_id}")
            return serialized
        except Exception as e:
            logger.error(f"Error retrieving messages from Zep thread {thread_id}: {e}")
            return []

    # ============= MEMORY RETRIEVAL =============

    async def get_memory(
        self,
        thread_id: str,
        lastn: Optional[int] = None,
    ) -> Optional[dict]:
        """
        Get memory for a thread (facts, summaries, relevant past conversations).
        This is the primary method for retrieving Zep's memory capabilities.

        Args:
            thread_id: Thread ID to get memory for
            lastn: Optional number of recent messages to include

        Returns:
            Dict with memory data including facts, summary, and messages
        """
        if not self.is_available():
            return None

        try:
            memory = await self.client.memory.get(session_id=thread_id, lastn=lastn)
            logger.debug(f"Retrieved memory for Zep thread {thread_id}")
            return memory.model_dump() if hasattr(memory, 'model_dump') else dict(memory)
        except Exception as e:
            logger.error(f"Error retrieving memory for thread {thread_id}: {e}")
            return None

    async def search_memory(
        self,
        thread_id: str,
        query: str,
        limit: int = 5,
    ) -> List[dict]:
        """
        Semantic search across thread memory.

        Args:
            thread_id: Thread to search within
            query: Search query
            limit: Number of results to return

        Returns:
            List of relevant memory entries
        """
        if not self.is_available():
            return []

        try:
            results = await self.client.memory.search_sessions(
                text=query,
                session_ids=[thread_id],
                limit=limit,
            )
            serialized = [r.model_dump() if hasattr(r, 'model_dump') else dict(r) for r in results]
            logger.debug(f"Found {len(serialized)} memory results for query: {query}")
            return serialized
        except Exception as e:
            logger.error(f"Error searching memory for thread {thread_id}: {e}")
            return []


# Singleton instance
_zep_client = None


def get_zep_client() -> ZepClient:
    """Get or create singleton Zep client instance."""
    global _zep_client
    if _zep_client is None:
        _zep_client = ZepClient()
    return _zep_client
