"""
Custom LangGraph checkpointer using Zep Cloud for storage.

This checkpointer implements the BaseCheckpointSaver interface to store
all LangGraph state in Zep Cloud, enabling full interrupt support and
message persistence without PostgreSQL.
"""

from typing import Optional, AsyncIterator, Any
from collections.abc import Sequence
from loguru import logger
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointTuple,
    CheckpointMetadata,
    get_checkpoint_id,
)
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langchain_core.messages import HumanMessage, AIMessage

from megamind.clients.zep_client import ZepClient


class ZepCheckpointSaver(BaseCheckpointSaver):
    """
    Custom LangGraph checkpointer using Zep Cloud for storage.

    Stores:
    - Complete checkpoint state in Zep session metadata
    - Messages in Zep message history (dual storage)
    - Supports interrupts via checkpoint persistence
    - Thread isolation with independent state

    Architecture:
    - Primary storage: checkpoint["channel_values"] in Zep session metadata
    - Secondary storage: Messages synced to Zep for memory features
    - No checkpoint history (only latest per thread)
    """

    def __init__(self, zep_client: ZepClient, serde=None):
        """
        Initialize Zep checkpointer.

        Args:
            zep_client: Initialized ZepClient instance
            serde: Serializer (defaults to JsonPlusSerializer)
        """
        super().__init__(serde=serde or JsonPlusSerializer())
        self.zep_client = zep_client
        logger.info("ZepCheckpointSaver initialized")

    async def setup(self) -> None:
        """
        Initialize Zep storage.

        No-op for Zep Cloud (sessions created on-demand).
        """
        logger.debug("Zep checkpointer setup - no initialization needed")

    # === CORE ASYNC METHODS ===

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """
        Retrieve the latest checkpoint tuple for a thread from Zep.

        Args:
            config: RunnableConfig with thread_id in configurable

        Returns:
            CheckpointTuple if found, None for new threads
        """
        try:
            thread_id = self._get_thread_id(config)
            logger.debug(f"Retrieving checkpoint for thread: {thread_id}")

            # Get Zep session (thread)
            session = await self.zep_client.get_thread(thread_id=thread_id)
            if not session:
                logger.debug(f"No Zep session found for thread: {thread_id} (new thread)")
                return None

            # Extract checkpoint from session metadata
            metadata_dict = session.get("metadata", {})
            checkpoint_data = metadata_dict.get("checkpoint")

            if not checkpoint_data:
                logger.debug(f"No checkpoint data in session metadata for thread: {thread_id}")
                return None

            # Deserialize checkpoint
            try:
                checkpoint = self.serde.loads_typed(
                    (checkpoint_data["type"], checkpoint_data["data"])
                )
            except Exception as e:
                logger.error(f"Failed to deserialize checkpoint for thread {thread_id}: {e}")
                return None

            # Build checkpoint metadata
            checkpoint_metadata = CheckpointMetadata(
                source=checkpoint_data.get("source", "loop"),
                step=checkpoint_data.get("step", 0),
                parents=checkpoint_data.get("parents", {}),
            )

            # Build parent config if exists
            parent_checkpoint_id = checkpoint.get("parent_checkpoint_id")
            parent_config = None
            if parent_checkpoint_id:
                parent_config = {
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_id": parent_checkpoint_id,
                    }
                }

            logger.debug(f"Successfully retrieved checkpoint for thread: {thread_id}")

            return CheckpointTuple(
                config=config,
                checkpoint=checkpoint,
                metadata=checkpoint_metadata,
                parent_config=parent_config,
                pending_writes=None,  # Zep doesn't support pending writes
            )

        except Exception as e:
            logger.error(f"Error retrieving checkpoint tuple: {e}")
            return None

    async def alist(
        self,
        config: RunnableConfig,
        *,
        filter: Optional[dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[CheckpointTuple]:
        """
        List checkpoints for a thread.

        Note: Zep doesn't support checkpoint history, so we return only
        the latest checkpoint if it exists.

        Args:
            config: RunnableConfig with thread_id
            filter: Not supported
            before: Not supported
            limit: Not supported

        Yields:
            CheckpointTuple for the latest checkpoint
        """
        try:
            checkpoint_tuple = await self.aget_tuple(config)
            if checkpoint_tuple:
                yield checkpoint_tuple
        except Exception as e:
            logger.error(f"Error listing checkpoints: {e}")
            return

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: dict[str, Any],
    ) -> RunnableConfig:
        """
        Store checkpoint in Zep session metadata.

        Also syncs messages to Zep message history for dual storage.

        Args:
            config: RunnableConfig with thread_id
            checkpoint: Complete checkpoint to store
            metadata: Checkpoint metadata
            new_versions: Channel versions (not used in Zep)

        Returns:
            Updated RunnableConfig with checkpoint_id
        """
        try:
            thread_id = self._get_thread_id(config)
            logger.debug(f"Storing checkpoint for thread: {thread_id}")

            # Serialize checkpoint
            checkpoint_type, checkpoint_data = self.serde.dumps_typed(checkpoint)

            # Prepare checkpoint metadata for storage
            checkpoint_metadata = {
                "type": checkpoint_type,
                "data": checkpoint_data,
                "source": metadata.get("source", "loop"),
                "step": metadata.get("step", 0),
                "parents": metadata.get("parents", {}),
                "checkpoint_id": checkpoint["id"],
                "timestamp": checkpoint["ts"],
            }

            # Check if session exists, create if needed
            existing_session = await self.zep_client.get_thread(thread_id=thread_id)

            if not existing_session:
                # Create new session
                # Extract user_id from checkpoint if available (might be in metadata)
                user_id = metadata.get("user_id", "default_user")

                logger.info(f"Creating new Zep session for thread: {thread_id}")
                await self.zep_client.get_or_create_thread(
                    thread_id=thread_id,
                    user_id=user_id,
                    metadata={
                        "checkpoint": checkpoint_metadata,
                        "checkpoint_ns": config["configurable"].get("checkpoint_ns", ""),
                    },
                )
            else:
                # Update existing session metadata
                existing_metadata = existing_session.get("metadata", {})
                existing_metadata["checkpoint"] = checkpoint_metadata
                existing_metadata["checkpoint_ns"] = config["configurable"].get(
                    "checkpoint_ns", ""
                )

                await self.zep_client.update_thread(
                    thread_id=thread_id, metadata=existing_metadata
                )

            # Sync messages to Zep (optional dual storage)
            messages = checkpoint.get("channel_values", {}).get("messages", [])
            if messages:
                await self._sync_messages_to_zep(thread_id, messages)

            logger.debug(
                f"Successfully stored checkpoint for thread: {thread_id} (checkpoint_id: {checkpoint['id']})"
            )

            # Return config with checkpoint_id
            return {
                "configurable": {
                    **config["configurable"],
                    "checkpoint_id": checkpoint["id"],
                }
            }

        except Exception as e:
            logger.error(f"Error storing checkpoint: {e}")
            raise

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """
        Store intermediate writes.

        Note: Zep doesn't support intermediate writes natively.
        This is a no-op as full checkpoint is stored via aput().

        Args:
            config: RunnableConfig with thread_id
            writes: Intermediate writes to store
            task_id: Task identifier
            task_path: Task path
        """
        # No-op for Zep (full checkpoint stored in aput)
        logger.debug(
            f"aput_writes called (no-op for Zep): {len(writes)} writes for task {task_id}"
        )

    # === HELPER METHODS ===

    def _get_thread_id(self, config: RunnableConfig) -> str:
        """Extract thread_id from config."""
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            raise ValueError("thread_id not found in config")
        return thread_id

    async def _sync_messages_to_zep(self, thread_id: str, messages: list) -> None:
        """
        Sync LangGraph messages to Zep message history.

        Converts LangChain message types to Zep format for dual storage.
        This enables Zep's memory features (facts, summaries, search).

        Args:
            thread_id: Thread to sync messages to
            messages: LangGraph messages to sync
        """
        try:
            zep_messages = []

            for msg in messages:
                # Only sync user and assistant messages
                if isinstance(msg, HumanMessage):
                    zep_messages.append({"role": "user", "content": str(msg.content)})
                elif isinstance(msg, AIMessage):
                    zep_messages.append(
                        {"role": "assistant", "content": str(msg.content)}
                    )

            if zep_messages:
                # Note: This adds ALL messages each time
                # Zep client should handle deduplication
                await self.zep_client.add_messages(
                    thread_id=thread_id, messages=zep_messages
                )
                logger.debug(f"Synced {len(zep_messages)} messages to Zep thread {thread_id}")

        except Exception as e:
            # Don't fail checkpoint storage if message sync fails
            logger.warning(f"Failed to sync messages to Zep for thread {thread_id}: {e}")
