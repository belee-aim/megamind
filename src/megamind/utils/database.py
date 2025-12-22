"""
Database utilities for connection pool management and health checking.
"""

from loguru import logger
from psycopg import AsyncConnection


async def configure_connection(conn: AsyncConnection) -> None:
    """
    Configure a new database connection with optimal settings.

    This callback is called by the connection pool when creating a new connection.
    It sets up TCP keepalives to prevent silent connection drops and configures
    statement timeout to prevent long-running queries from blocking.

    Args:
        conn: The newly created database connection
    """
    try:
        # TCP Keepalives: Detect and close broken connections
        # keepalives_idle: Start sending keepalive packets after 30s of inactivity
        await conn.execute("SET tcp_keepalives_idle = 30")

        # keepalives_interval: Send keepalive packet every 10s after idle period
        await conn.execute("SET tcp_keepalives_interval = 10")

        # keepalives_count: Declare connection dead after 5 failed keepalive attempts
        await conn.execute("SET tcp_keepalives_count = 5")

        # Statement timeout: Kill queries running longer than 60 seconds
        # This prevents runaway queries from blocking connections
        await conn.execute("SET statement_timeout = 60000")

        # Commit to exit the implicit transaction started by SET commands
        await conn.commit()

        logger.debug("Database connection configured successfully")
    except Exception as e:
        logger.error(f"Failed to configure database connection: {e}")
        raise


async def check_connection(conn: AsyncConnection) -> None:
    """
    Verify that a connection from the pool is still healthy.

    This callback is called by the connection pool before giving a connection
    to a client. If the check fails, the pool will discard the broken connection
    and create a new one.

    Args:
        conn: The connection to check

    Raises:
        Exception: If the connection is not healthy (will be caught by pool)
    """
    try:
        # Simple query to verify connection is alive and responsive
        await conn.execute("SELECT 1")
        logger.debug("Connection health check passed")
    except Exception as e:
        logger.warning(f"Connection health check failed: {e}")
        # Re-raise so pool can replace the broken connection
        raise


def log_pool_stats(pool) -> None:
    """
    Log current connection pool statistics for monitoring.

    Args:
        pool: The AsyncConnectionPool instance
    """
    try:
        # Note: psycopg AsyncConnectionPool doesn't expose these stats directly
        # This is a placeholder for future monitoring implementation
        logger.debug("Connection pool statistics logged")
    except Exception as e:
        logger.warning(f"Failed to log pool statistics: {e}")
