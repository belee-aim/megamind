from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv(override=True)


class Settings(BaseSettings):
    # LLM Provider Configuration
    provider: str = "GEMINI"  # GEMINI, DEEPSEEK, CLAUDE, or KIMI
    api_key: str = ""  # Generic API key for the selected provider
    model: str = "gemini-2.5-flash"  # Model name for the selected provider
    embedding_model: str = "models/embedding-001"  # Embedding model name

    # Legacy Gemini configuration (for backward compatibility)
    google_api_key: str = ""

    # Frappe/ERPNext Configuration
    frappe_url: str
    frappe_api_key: str
    frappe_api_secret: str
    frappe_auth_mode: str = "jwt"
    frappe_mcp_server_path: str = "none"

    # Supabase Configuration
    supabase_url: str
    supabase_key: str
    supabase_connection_string: str
    supabase_db_url: str = (
        ""  # Database URL for connection pool (if different from connection_string)
    )

    # Database Connection Pool Configuration
    db_pool_min_size: int = 2  # Minimum number of connections to keep in the pool
    db_pool_max_size: int = 100  # Maximum number of connections allowed in the pool
    db_pool_max_waiting: int = 50  # Maximum number of requests waiting for a connection
    db_pool_max_lifetime: float = (
        1800.0  # Maximum lifetime of a connection in seconds (30 min)
    )
    db_pool_max_idle: float = (
        180.0  # Maximum idle time before closing a connection (3 min)
    )
    db_pool_reconnect_timeout: float = (
        300.0  # Timeout for reconnection attempts (5 min)
    )
    db_pool_timeout: float = 30.0  # Timeout for acquiring a connection from the pool
    db_pool_num_workers: int = 3  # Number of background workers for pool maintenance

    # Application Configuration
    log_level: str = "INFO"
    json_logs: bool = False
    minion_api_url: str = "http://localhost:8000"
    titan_api_url: str = "http://localhost:8001"
    tenant_id: str = "aimlink"

    # Sentry Configuration
    sentry_dsn: str = ""
    environment: str = "development"
    sentry_traces_sample_rate: float = 1.0  # 1.0 = 100%, 0.1 = 10%

    # Firebase Configuration
    firebase_database_url: str = ""
    firebase_credentials_base64: str = ""

    # Neo4J Configuration
    neo4j_uri: str = "bolt://localhost:7688"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "neo4j_password"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
