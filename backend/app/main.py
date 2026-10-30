"""SafeMed API entry point."""
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db

app = FastAPI(
    title=f"{settings.PROJECT_NAME} API",
    description=(
        "Continuous medication safety monitoring and caregiver alerts. "
        "Safety findings come from authoritative data evaluated by deterministic "
        "rules. This system does not diagnose, prescribe, or advise changing a "
        "medication."
    ),
    version="0.1.0",
)

# The React development server runs on a different port, so the browser treats
# it as a different origin. These rules tell the browser those requests are
# allowed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
def health(db: Session = Depends(get_db)) -> dict:
    """Liveness check used by developers, monitoring, and the demo status panel.

    Reports whether the API is up AND whether it can actually reach the
    database. An API that answers while its database is unreachable is not
    healthy, so both are reported separately.
    """
    try:
        db.execute(text("SELECT 1"))
        database = "connected"
    except Exception as exc:  # noqa: BLE001 - we want the reason in the response
        database = f"unavailable: {type(exc).__name__}"

    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "database": database,
    }


@app.get("/", tags=["system"])
def root() -> dict:
    return {
        "service": settings.PROJECT_NAME,
        "docs": "/docs",
        "health": "/health",
    }
