from functools import lru_cache
import secrets
import json
import os

from pydantic import field_validator, ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    app_name: str = "Plataforma de Atención de Emergencias API"
    app_env: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # CORS origins - will be parsed from comma-separated string
    backend_cors_origins: str = "http://localhost:3000,http://localhost:4200,http://localhost:5173"

    # Security: Must be different in production
    secret_key: str = ""  # Will be generated if empty
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    reset_token_expire_minutes: int = 15

    # Database: Must be provided via environment
    database_url: str = ""

    # Email Configuration
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    frontend_url: str = "http://localhost:5173"

    # Cloudflare R2 (Optional)
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = ""
    r2_public_base_url: str = ""

    # Firebase Cloud Messaging (Optional)
    fcm_project_id: str = ""
    fcm_client_email: str = ""
    fcm_private_key: str = ""

    # Firebase Cloud Messaging Configuration - NEW
    FCM_ENABLED: bool = False
    FIREBASE_CREDENTIALS_JSON: str = ""  # JSON string o ruta a archivo
    PUSH_DEFAULT_TTL_SECONDS: int = 3600

    # AI Services (Optional)
    ai_text_audio_provider: str = "faster_whisper"
    ai_text_audio_api_key: str = ""
    ai_text_audio_base_url: str = ""

    ai_image_service_url: str = "http://localhost:8090"
    ai_image_service_api_key: str = ""

    # Speech-to-Text (STT) Configuration - faster-whisper
    stt_model_size: str = "base"  # tiny, base, small, medium, large
    stt_device: str = "cpu"  # cpu, cuda, mps
    stt_compute_type: str = "int8"  # int8, int16, float16, float32
    stt_language: str = "es"  # Language code (es for Spanish)
    stt_beam_size: int = 1  # Beam size for faster inference
    stt_vad_filter: bool = True  # Voice Activity Detection filter
    stt_chunk_length_ms: int = 30000  # 30 seconds
    stt_max_file_size_mb: float = 50.0  # Max audio file size
    stt_timeout_seconds: int = 60  # Timeout for transcription

    # Text Classification Configuration
    text_classification_timeout_seconds: int = 30
    text_classification_confidence_threshold: float = 0.5

    # Groq - Clasificación de urgencia por texto (LLM)
    groq_api_key: str = "colocar api key aqui"
    groq_model: str = "llama-3.1-8b-instant"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_timeout_seconds: int = 30

    model_config = ConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        case_sensitive=False,
        extra="ignore"
    )

    @field_validator("secret_key", mode="before")
    @classmethod
    def set_secret_key(cls, v):
        """Generate secret key if not provided"""
        if not v or v == "":
            return secrets.token_urlsafe(32)
        return v

    @field_validator("FIREBASE_CREDENTIALS_JSON", mode="before")
    @classmethod
    def load_firebase_credentials(cls, v):
        """Load Firebase credentials from file or use JSON string"""
        if not v:
            # Intentar cargar desde archivo por defecto
            firebase_file = "firebase-credentials.json"
            if os.path.exists(firebase_file):
                try:
                    with open(firebase_file, 'r') as f:
                        creds = json.load(f)
                    return json.dumps(creds)
                except Exception as e:
                    print(f"⚠️ No se pudo cargar firebase-credentials.json: {e}")
                    return ""
            return ""
        
        # Si es una ruta a archivo, cargar desde allí
        if isinstance(v, str) and v.endswith('.json') and os.path.exists(v):
            try:
                with open(v, 'r') as f:
                    creds = json.load(f)
                return json.dumps(creds)
            except Exception as e:
                print(f"⚠️ No se pudo cargar archivo Firebase: {e}")
                return v
        
        # Si es JSON string, devolverlo tal cual
        return v

    def get_cors_origins(self) -> list[str]:
        """Parse and return CORS origins as list"""
        if isinstance(self.backend_cors_origins, str):
            return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]
        return self.backend_cors_origins


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
