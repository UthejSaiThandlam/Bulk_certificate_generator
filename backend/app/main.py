import os
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import settings
from app.database import engine, Base
from app.routers import certificates
from app.services.certificate_generator import CertificateGenerator
from app.services.job_processor import resume_interrupted_jobs


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database tables exist
    Base.metadata.create_all(bind=engine)

    # Ensure generated and templates storage directories exist
    os.makedirs(settings.GENERATED_DIR, exist_ok=True)
    os.makedirs(settings.TEMPLATES_DIR, exist_ok=True)

    # 1. Startup validation: fail fast if ReportLab / PDF engine fails
    CertificateGenerator.validate_template_at_startup()

    # 2. Crash recovery: resume any interrupted jobs in a non-blocking background thread
    recovery_thread = threading.Thread(target=resume_interrupted_jobs, daemon=True)
    recovery_thread.start()

    yield


app = FastAPI(
    title="Bulk Certificate Generator API",
    description="High-performance FastAPI service for bulk PDF certificate issuance, tracking, and verification.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS Middleware (credentials set to False when allowing all origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# API Routers
app.include_router(certificates.router)


@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint verifying application and database connectivity."""
    db_status = "connected"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
        "service": "Bulk Certificate Generator",
        "version": "1.0.0",
    }


# Mount frontend directory for static single-page app serving (must be mounted after routers)
if os.path.isdir(settings.FRONTEND_DIR):
    app.mount(
        "/",
        StaticFiles(directory=str(settings.FRONTEND_DIR), html=True),
        name="frontend",
    )
