"""
API endpoints for Zep user, thread, and message management.
Provides CRUD operations for Zep memory system.
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger

from megamind.clients.zep_client import get_zep_client
from megamind.models.requests import (
    ZepUserCreateRequest,
    ZepThreadCreateRequest,
    ZepMessageAddRequest,
)
from megamind.models.responses import MainResponse

router = APIRouter()


# ============= USER ENDPOINTS =============


@router.post("/users")
async def create_user(
    request: Request,
    request_data: ZepUserCreateRequest,
):
    """
    Create a new Zep user.

    **Note:** Users are auto-created when they start a thread,
    so this endpoint is mainly for explicit user management.
    """
    try:
        logger.info(f"Creating Zep user: {request_data.user_id}")

        zep_client = get_zep_client()
        if not zep_client.is_available():
            raise HTTPException(
                status_code=503, detail="Zep service not configured or unavailable"
            )

        user = await zep_client.get_or_create_user(
            user_id=request_data.user_id,
            email=request_data.email,
            first_name=request_data.first_name,
            last_name=request_data.last_name,
            metadata=request_data.metadata,
        )

        if not user:
            raise HTTPException(status_code=500, detail="Failed to create Zep user")

        logger.info(f"Successfully created Zep user: {request_data.user_id}")

        return MainResponse(
            message="User created successfully",
            response=user,
        ).model_dump()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating Zep user: {e}")
        return JSONResponse(
            status_code=500,
            content=MainResponse(
                message="Error",
                error=f"Failed to create user: {str(e)}",
            ).model_dump(),
        )


@router.get("/users/{user_id}")
async def get_user(
    request: Request,
    user_id: str,
):
    """Retrieve a Zep user by ID."""
    try:
        logger.debug(f"Retrieving Zep user: {user_id}")

        zep_client = get_zep_client()
        if not zep_client.is_available():
            raise HTTPException(
                status_code=503, detail="Zep service not configured or unavailable"
            )

        user = await zep_client.get_user(user_id=user_id)

        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")

        return MainResponse(
            message="User retrieved successfully",
            response=user,
        ).model_dump()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving Zep user: {e}")
        return JSONResponse(
            status_code=500,
            content=MainResponse(
                message="Error",
                error=f"Failed to retrieve user: {str(e)}",
            ).model_dump(),
        )


@router.delete("/users/{user_id}")
async def delete_user(
    request: Request,
    user_id: str,
):
    """Delete a Zep user and all associated threads."""
    try:
        logger.info(f"Deleting Zep user: {user_id}")

        zep_client = get_zep_client()
        if not zep_client.is_available():
            raise HTTPException(
                status_code=503, detail="Zep service not configured or unavailable"
            )

        success = await zep_client.delete_user(user_id=user_id)

        if not success:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")

        logger.info(f"Successfully deleted Zep user: {user_id}")

        return MainResponse(
            message="User deleted successfully",
        ).model_dump()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting Zep user: {e}")
        return JSONResponse(
            status_code=500,
            content=MainResponse(
                message="Error",
                error=f"Failed to delete user: {str(e)}",
            ).model_dump(),
        )


# ============= THREAD ENDPOINTS =============


@router.post("/threads")
async def create_thread(
    request: Request,
    request_data: ZepThreadCreateRequest,
):
    """
    Create a new Zep thread.

    **Note:** Threads are auto-created when users start conversations,
    so this endpoint is mainly for explicit thread management.
    """
    try:
        logger.info(f"Creating Zep thread: {request_data.thread_id}")

        zep_client = get_zep_client()
        if not zep_client.is_available():
            raise HTTPException(
                status_code=503, detail="Zep service not configured or unavailable"
            )

        thread = await zep_client.get_or_create_thread(
            thread_id=request_data.thread_id,
            user_id=request_data.user_id,
        )

        if not thread:
            raise HTTPException(status_code=500, detail="Failed to create Zep thread")

        logger.info(f"Successfully created Zep thread: {request_data.thread_id}")

        return MainResponse(
            message="Thread created successfully",
            response=thread,
        ).model_dump()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating Zep thread: {e}")
        return JSONResponse(
            status_code=500,
            content=MainResponse(
                message="Error",
                error=f"Failed to create thread: {str(e)}",
            ).model_dump(),
        )


@router.get("/threads/{thread_id}/messages")
async def get_thread_messages(
    request: Request,
    thread_id: str,
    limit: int = 50,
    lastn: int = None,
):
    """Retrieve messages from a Zep thread."""
    try:
        logger.debug(f"Retrieving messages for Zep thread: {thread_id}")

        zep_client = get_zep_client()
        if not zep_client.is_available():
            raise HTTPException(
                status_code=503, detail="Zep service not configured or unavailable"
            )

        messages = await zep_client.get_thread_messages(
            thread_id=thread_id,
            limit=limit,
            lastn=lastn,
        )

        return MainResponse(
            message=f"Retrieved {len(messages)} messages",
            response={"messages": messages, "count": len(messages)},
        ).model_dump()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving Zep thread messages: {e}")
        return JSONResponse(
            status_code=500,
            content=MainResponse(
                message="Error",
                error=f"Failed to retrieve messages: {str(e)}",
            ).model_dump(),
        )


@router.delete("/threads/{thread_id}")
async def delete_thread(
    request: Request,
    thread_id: str,
):
    """Delete a Zep thread and all associated messages."""
    try:
        logger.info(f"Deleting Zep thread: {thread_id}")

        zep_client = get_zep_client()
        if not zep_client.is_available():
            raise HTTPException(
                status_code=503, detail="Zep service not configured or unavailable"
            )

        success = await zep_client.delete_thread(thread_id=thread_id)

        if not success:
            raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")

        logger.info(f"Successfully deleted Zep thread: {thread_id}")

        return MainResponse(
            message="Thread deleted successfully",
        ).model_dump()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting Zep thread: {e}")
        return JSONResponse(
            status_code=500,
            content=MainResponse(
                message="Error",
                error=f"Failed to delete thread: {str(e)}",
            ).model_dump(),
        )


@router.get("/threads")
async def list_threads(
    request: Request,
    user_id: str = None,
    limit: int = 100,
    page: int = 1,
):
    """List threads, optionally filtered by user."""
    try:
        logger.debug(
            f"Listing Zep threads (user_id={user_id}, limit={limit}, page={page})"
        )

        zep_client = get_zep_client()
        if not zep_client.is_available():
            raise HTTPException(
                status_code=503, detail="Zep service not configured or unavailable"
            )

        threads = await zep_client.list_threads(user_id=user_id, limit=limit, page=page)

        return MainResponse(
            message=f"Retrieved {len(threads)} threads",
            response={"threads": threads, "count": len(threads), "page": page},
        ).model_dump()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing Zep threads: {e}")
        return JSONResponse(
            status_code=500,
            content=MainResponse(
                message="Error",
                error=f"Failed to list threads: {str(e)}",
            ).model_dump(),
        )


# ============= MESSAGE ENDPOINTS =============


@router.post("/messages")
async def add_messages(
    request: Request,
    request_data: ZepMessageAddRequest,
):
    """Add messages to a Zep thread for memory building."""
    try:
        logger.info(f"Adding messages to Zep thread: {request_data.thread_id}")

        zep_client = get_zep_client()
        if not zep_client.is_available():
            raise HTTPException(
                status_code=503, detail="Zep service not configured or unavailable"
            )

        success = await zep_client.add_messages(
            thread_id=request_data.thread_id,
            messages=request_data.messages,
        )

        if not success:
            raise HTTPException(
                status_code=500, detail="Failed to add messages to thread"
            )

        logger.info(f"Successfully added {len(request_data.messages)} messages")

        return MainResponse(
            message=f"Added {len(request_data.messages)} messages successfully",
        ).model_dump()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding messages to Zep thread: {e}")
        return JSONResponse(
            status_code=500,
            content=MainResponse(
                message="Error",
                error=f"Failed to add messages: {str(e)}",
            ).model_dump(),
        )


# ============= CONTEXT ENDPOINTS =============


@router.get("/threads/{thread_id}/context")
async def get_thread_context(
    request: Request,
    thread_id: str,
    min_rating: float = None,
):
    """
    Get context for a thread (facts, summaries).
    This is Zep's primary memory retrieval capability.
    """
    try:
        logger.debug(f"Retrieving context for Zep thread: {thread_id}")

        zep_client = get_zep_client()
        if not zep_client.is_available():
            raise HTTPException(
                status_code=503, detail="Zep service not configured or unavailable"
            )

        context = await zep_client.get_context(
            thread_id=thread_id,
            min_rating=min_rating,
        )

        if not context:
            raise HTTPException(
                status_code=404, detail=f"No context found for thread {thread_id}"
            )

        return MainResponse(
            message="Context retrieved successfully",
            response=context,
        ).model_dump()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving context: {e}")
        return JSONResponse(
            status_code=500,
            content=MainResponse(
                message="Error",
                error=f"Failed to retrieve context: {str(e)}",
            ).model_dump(),
        )
