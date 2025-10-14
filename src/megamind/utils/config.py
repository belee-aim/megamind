from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv(override=True)


class Settings(BaseSettings):
    google_api_key: str
    frappe_url: str
    frappe_api_key: str
    frappe_api_secret: str
    frappe_auth_mode: str = "cookie"
    supabase_url: str
    supabase_key: str
    supabase_connection_string: str
    log_level: str = "INFO"
    json_logs: bool = False
    llama_cloud_api_key: str
    frappe_mcp_server_path: str = "none"
    frappe_assistant_core_server_path: str = "none"
    minion_api_url: str = "http://localhost:8000"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
