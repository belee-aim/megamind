from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()  

class Settings(BaseSettings):
    google_api_key: str
    frappe_url: str
    frappe_api_key: str
    frappe_api_secret: str
    supabase_url: str
    supabase_key: str
    supabase_connection_string: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings() # type: ignore
