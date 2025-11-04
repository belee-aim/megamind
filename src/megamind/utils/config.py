from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv(override=True)


class Settings(BaseSettings):
    # LLM Provider Configuration
    provider: str = "GEMINI"  # GEMINI, DEEPSEEK, or CLAUDE
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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
