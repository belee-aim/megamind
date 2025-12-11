"""
Zep Cloud client for Knowledge Graph-based memory and thread management.
Uses the new Zep v3 API for threads, messages, and graph operations.
"""

from typing import Optional, List
from loguru import logger
from zep_cloud.client import AsyncZep
from zep_cloud import Message

from megamind.utils.config import settings


class ZepClient:
    """
    Client for interacting with Zep Cloud.

    Zep provides:
    - Thread-based conversation management
    - Message storage and retrieval
    - Graph-based knowledge storage (episodes, facts, entities)
    - Per-user knowledge graph isolation
    - Semantic search across user's memory
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Zep client.

        Args:
            api_key: Optional API key override (defaults to settings.zep_api_key)
        """
        self.api_key = api_key or settings.zep_api_key

        if not self.api_key:
            logger.warning("Zep API key not configured. Zep features will be disabled.")
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
        email: str = "",
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[dict]:
        """
        Get existing user or create if doesn't exist.

        Args:
            user_id: Unique user identifier
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
                return user.model_dump() if hasattr(user, "model_dump") else dict(user)
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
                return user.model_dump() if hasattr(user, "model_dump") else dict(user)

        except Exception as e:
            logger.error(f"Error creating/retrieving Zep user {user_id}: {e}")
            return None

    async def get_user(self, user_id: str) -> Optional[dict]:
        """Retrieve user by ID."""
        if not self.is_available():
            return None

        try:
            user = await self.client.user.get(user_id=user_id)
            return user.model_dump() if hasattr(user, "model_dump") else dict(user)
        except Exception as e:
            logger.debug(f"User {user_id} not found: {e}")
            return None

    async def delete_user(self, user_id: str) -> bool:
        """Delete a user and their associated data."""
        if not self.is_available():
            return False

        try:
            await self.client.user.delete(user_id=user_id)
            logger.info(f"Deleted Zep user: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting Zep user {user_id}: {e}")
            return False

    # ============= THREAD MANAGEMENT =============

    async def create_thread(
        self,
        thread_id: str,
        user_id: str,
    ) -> Optional[dict]:
        """
        Create a new conversation thread.

        Args:
            thread_id: Unique thread identifier
            user_id: User who owns this thread

        Returns:
            Thread dict if successful, None otherwise
        """
        if not self.is_available():
            return None

        try:
            thread = await self.client.thread.create(
                thread_id=thread_id,
                user_id=user_id,
            )
            logger.info(f"Created Zep thread: {thread_id} for user: {user_id}")
            return (
                thread.model_dump() if hasattr(thread, "model_dump") else dict(thread)
            )
        except Exception as e:
            logger.error(f"Error creating thread {thread_id}: {e}")
            return None

    async def get_or_create_thread(
        self,
        thread_id: str,
        user_id: str,
    ) -> Optional[dict]:
        """
        Get existing thread or create if doesn't exist.

        Args:
            thread_id: Unique thread identifier
            user_id: User who owns this thread

        Returns:
            Thread dict if successful, None otherwise
        """
        if not self.is_available():
            return None

        try:
            # Try to get existing thread by getting its messages
            try:
                # thread.get returns messages, if it works the thread exists
                await self.client.thread.get(thread_id=thread_id, lastn=1)
                logger.debug(f"Thread {thread_id} exists")
                return {"thread_id": thread_id, "user_id": user_id}
            except Exception:
                # Thread doesn't exist, create it
                return await self.create_thread(thread_id=thread_id, user_id=user_id)
        except Exception as e:
            logger.error(f"Error in get_or_create_thread {thread_id}: {e}")
            return None

    async def get_thread_messages(
        self,
        thread_id: str,
        limit: int = 50,
        lastn: Optional[int] = None,
    ) -> List[dict]:
        """
        Get messages from a thread.

        Args:
            thread_id: Thread ID
            limit: Maximum messages to return
            lastn: Get N most recent messages (overrides limit)

        Returns:
            List of message dicts
        """
        if not self.is_available():
            return []

        try:
            response = await self.client.thread.get(
                thread_id=thread_id,
                limit=limit if not lastn else None,
                lastn=lastn,
            )

            if hasattr(response, "messages") and response.messages:
                return [
                    msg.model_dump() if hasattr(msg, "model_dump") else dict(msg)
                    for msg in response.messages
                ]
            return []
        except Exception as e:
            logger.error(f"Error getting messages for thread {thread_id}: {e}")
            return []

    async def list_threads(
        self,
        user_id: Optional[str] = None,
        limit: int = 100,
        page: int = 1,
    ) -> List[dict]:
        """
        List threads, optionally filtered by user.

        Args:
            user_id: Optional user ID to filter by
            limit: Maximum threads to return
            page: Page number for pagination

        Returns:
            List of thread dicts
        """
        if not self.is_available():
            return []

        try:
            # Note: list_all may not support user_id filtering directly
            response = await self.client.thread.list_all(
                page_number=page,
                page_size=limit,
            )

            threads = []
            if hasattr(response, "threads") and response.threads:
                for thread in response.threads:
                    thread_dict = (
                        thread.model_dump()
                        if hasattr(thread, "model_dump")
                        else dict(thread)
                    )
                    # Filter by user_id if specified
                    if user_id is None or thread_dict.get("user_id") == user_id:
                        threads.append(thread_dict)

            return threads
        except Exception as e:
            logger.error(f"Error listing threads: {e}")
            return []

    async def delete_thread(self, thread_id: str) -> bool:
        """Delete a thread and all its messages."""
        if not self.is_available():
            return False

        try:
            await self.client.thread.delete(thread_id=thread_id)
            logger.info(f"Deleted Zep thread: {thread_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting thread {thread_id}: {e}")
            return False

    # ============= MESSAGE MANAGEMENT =============

    async def add_message(
        self,
        thread_id: str,
        role: str,
        content: str,
    ) -> bool:
        """
        Add a single message to a thread.

        Args:
            thread_id: Thread to add message to
            role: Message role ('user', 'assistant', 'system')
            content: Message content

        Returns:
            True if successful
        """
        if not self.is_available():
            return False

        try:
            await self.client.thread.add_messages(
                thread_id=thread_id,
                messages=[
                    Message(
                        role=role,
                        content=content,
                    )
                ],
            )
            logger.debug(f"Added {role} message to thread {thread_id}")
            return True
        except Exception as e:
            logger.error(f"Error adding message to thread {thread_id}: {e}")
            return False

    async def add_messages(
        self,
        thread_id: str,
        messages: List[dict],
    ) -> bool:
        """
        Add multiple messages to a thread.

        Args:
            thread_id: Thread to add messages to
            messages: List of message dicts with 'role' and 'content' keys

        Returns:
            True if successful
        """
        if not self.is_available() or not messages:
            return False

        try:
            zep_messages = [
                Message(
                    role=msg.get("role", "user"),
                    content=msg.get("content", ""),
                )
                for msg in messages
            ]

            await self.client.thread.add_messages(
                thread_id=thread_id,
                messages=zep_messages,
            )
            logger.debug(f"Added {len(messages)} messages to thread {thread_id}")
            return True
        except Exception as e:
            logger.error(f"Error adding messages to thread {thread_id}: {e}")
            return False

    # ============= CONTEXT & SEARCH =============

    async def get_context(
        self,
        thread_id: str,
        min_rating: Optional[float] = None,
    ) -> Optional[dict]:
        """
        Get relevant context for a thread (facts, summaries).

        Args:
            thread_id: Thread ID
            min_rating: Minimum fact rating to include

        Returns:
            Context dict with facts and summary
        """
        if not self.is_available():
            return None

        try:
            context = await self.client.thread.get_context(
                thread_id=thread_id,
                min_rating=min_rating,
            )
            return (
                context.model_dump()
                if hasattr(context, "model_dump")
                else dict(context)
            )
        except Exception as e:
            logger.error(f"Error getting context for thread {thread_id}: {e}")
            return None

    async def search_graph(
        self,
        query: str,
        user_id: Optional[str] = None,
        graph_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[dict]:
        """
        Search the knowledge graph using Zep's graph search.

        Optimized for performance - uses minimal parameters.
        See: https://help.getzep.com/performance

        Args:
            query: Concise search query (keep it focused for best results)
            user_id: User ID for user-specific graph search
            graph_id: Graph ID for shared/company graph search
            limit: Maximum results (default: 10, max: 50)

        Returns:
            List of search results
        """
        if not self.is_available():
            return []

        if not user_id and not graph_id:
            logger.error("Either user_id or graph_id must be provided for graph search")
            return []

        try:
            # Minimal search params for optimal performance
            search_kwargs = {
                "query": query,
                "limit": limit,
            }

            if user_id:
                search_kwargs["user_id"] = user_id
            if graph_id:
                search_kwargs["graph_id"] = graph_id

            results = await self.client.graph.search(**search_kwargs)

            # Extract edges from results
            if hasattr(results, "edges"):
                return [
                    edge.model_dump() if hasattr(edge, "model_dump") else dict(edge)
                    for edge in (results.edges or [])
                ]

            return []
        except Exception as e:
            logger.error(f"Error searching Zep graph: {e}")
            return []

    async def warm_user_cache(self, user_id: str) -> bool:
        """
        Warm the user's cache for faster retrieval.

        Call this when a user logs in or opens the app.
        Zep moves user data to a "hot" cache tier for faster access.
        See: https://help.getzep.com/performance

        Args:
            user_id: User ID to warm cache for

        Returns:
            True if successful
        """
        if not self.is_available():
            return False

        try:
            await self.client.user.warm(user_id=user_id)
            logger.debug(f"Warmed cache for user: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error warming cache for user {user_id}: {e}")
            return False


# Singleton instance
_zep_client: Optional[ZepClient] = None


def get_zep_client() -> ZepClient:
    """Get the singleton Zep client instance."""
    global _zep_client
    if _zep_client is None:
        _zep_client = ZepClient()
    return _zep_client
