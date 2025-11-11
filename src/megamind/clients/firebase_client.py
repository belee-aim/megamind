import asyncio
import base64
import json
from firebase_admin import credentials, db, initialize_app
from loguru import logger
from typing import Optional
from megamind.utils.config import settings


class FirebaseClient:
    """
    Singleton client for Firebase Realtime Database.
    Manages interrupt_state for human-in-the-loop flows.
    """

    _instance: Optional["FirebaseClient"] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            try:
                logger.info("Initializing Firebase client")

                # Decode base64-encoded credentials
                try:
                    credentials_json = base64.b64decode(
                        settings.firebase_credentials_base64
                    ).decode("utf-8")
                    credentials_dict = json.loads(credentials_json)
                except Exception as decode_error:
                    logger.error(
                        f"Failed to decode Firebase credentials: {decode_error}"
                    )
                    raise ValueError(
                        "Invalid Firebase credentials base64 encoding"
                    ) from decode_error

                # Initialize Firebase Admin SDK
                cred = credentials.Certificate(credentials_dict)
                initialize_app(
                    cred, {"databaseURL": settings.firebase_database_url}
                )

                self._initialized = True
                logger.info("Firebase client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Firebase: {e}")
                raise

    async def set_interrupt_state(self, thread_id: str, interrupted: bool) -> None:
        """
        Set interrupt state for a thread.

        Args:
            thread_id: LangGraph thread ID
            interrupted: True = waiting for consent, False = resolved
        """
        try:
            ref = db.reference(f"/interrupt_state/{thread_id}")

            # Firebase SDK is synchronous, run in thread pool
            await asyncio.to_thread(ref.set, interrupted)

            logger.info(
                f"Firebase: Set interrupt_state/{thread_id} = {interrupted}"
            )

        except Exception as e:
            logger.error(
                f"Firebase: Failed to set interrupt state for {thread_id}: {e}"
            )
            # Don't raise - Firebase failure shouldn't break the graph

    async def get_interrupt_state(self, thread_id: str) -> Optional[bool]:
        """Get interrupt state for a thread."""
        try:
            ref = db.reference(f"/interrupt_state/{thread_id}")
            state = await asyncio.to_thread(ref.get)
            return state
        except Exception as e:
            logger.error(
                f"Firebase: Failed to get interrupt state for {thread_id}: {e}"
            )
            return None

    async def clear_interrupt_state(self, thread_id: str) -> None:
        """Remove interrupt state for a thread."""
        try:
            ref = db.reference(f"/interrupt_state/{thread_id}")
            await asyncio.to_thread(ref.delete)
            logger.info(f"Firebase: Cleared interrupt_state/{thread_id}")
        except Exception as e:
            logger.error(
                f"Firebase: Failed to clear interrupt state for {thread_id}: {e}"
            )


# Global singleton instance
firebase_client = FirebaseClient()
