"""
FastAPI app assembly — routers imported here only (Sprint Plan §4: "a
module's folder is only ever edited by its owner... app/main.py and
core/ are the two shared touch-points").
"""
import logging

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.router import auth_router, users_router, audit_router
from app.core.settings_router import router as settings_router

from app.core.config import get_settings
from app.core.db import get_db
from app.core.exceptions import DomainError

settings = get_settings()
logger = logging.getLogger("app")

app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------- #
# Exception handlers
# --------------------------------------------------------------------- #
@app.exception_handler(DomainError)
def handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
    """SDD Table 1.3: map each domain exception to its status code."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.exception_handler(Exception)
async def handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
    """SDD 2.4: log unexpected errors, return a generic 500 without details."""
    logger.exception("Unhandled error")
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred."},
    )


# --------------------------------------------------------------------- #
# Health
# --------------------------------------------------------------------- #
@app.get("/health", tags=["health"])
def health(db: Session = Depends(get_db)) -> dict:
    """Actually check the DB so an orchestrator knows when it's gone."""
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


# --------------------------------------------------------------------- #
# Routers
# --------------------------------------------------------------------- #
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(users_router, prefix=settings.API_V1_PREFIX)
app.include_router(audit_router, prefix=settings.API_V1_PREFIX)
app.include_router(settings_router, prefix=settings.API_V1_PREFIX)

# Other packages' routers (inventory, expiry_reorder, notification, clinic,
# reporting) are added here by their owners as they're built — each one
# is a single extra `app.include_router(...)` line, nothing else in this
# file should need to change.