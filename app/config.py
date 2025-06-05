from pydantic_settings import BaseSettings, SettingsConfigDict
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

class Settings(BaseSettings):
    google_api_key: str
    supabase_jwt_secret: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

google_api_key = os.getenv("GOOGLE_API_KEY")
supabase_jwt_secret = os.getenv("SUPABASE_JWT_SECRET")

if not google_api_key or not supabase_jwt_secret:
    raise ValueError("Environment variables GOOGLE_API_KEY and SUPABASE_JWT_SECRET must be set.")

settings = Settings(google_api_key=google_api_key, supabase_jwt_secret=supabase_jwt_secret)
