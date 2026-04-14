from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file explicitly
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.database import SessionLocal
from app.services.fcm_service import FCMService


configure_logging()
logger = logging.getLogger(__name__)

# Log database configuration (masked for security)
if settings.database_url:
    db_url_masked = settings.database_url.split("@")[0] + "@***" if "@" in settings.database_url else "***"
    logger.info(f"Database configured: {db_url_masked}")
else:
    logger.warning("WARNING: DATABASE_URL is not configured!")

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware must be added FIRST
cors_origins = settings.get_cors_origins()
logger.info(f"CORS origins configured: {cors_origins}")

# In development, allow any origin (for Flutter dynamic ports)
if settings.app_env == "development":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins in development
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
        max_age=3600,
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
        max_age=3600,
    )

app.include_router(api_router, prefix=settings.api_v1_prefix)

# Initialize Firebase Cloud Messaging on startup
@app.on_event("startup")
def startup_event():
    """Inicializa FCM y otros servicios al arrancar"""
    logger.info("Inicializando servicios...")
    FCMService.initialize()
    logger.info("Servicios inicializados correctamente")


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "environment": settings.app_env}


@app.get("/db-check", tags=["Diagnostics"])
def db_check() -> dict[str, str]:
    """Verifica la conexión a la base de datos"""
    try:
        db = SessionLocal()
        result = db.execute(text("SELECT 1"))
        db.close()
        return {"status": "connected", "database": "ok"}
    except Exception as e:
        return {"status": "error", "database": str(e)}
