"""Application assembly. Run `python -m uvicorn app.main:app` from the project root."""

import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.dependencies import DbSession
from app.api.routers import auth, products, sellers
from app.core.config import get_settings

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """A factory lets tests create an app with their own dependency overrides."""
    settings = get_settings()
    application = FastAPI(
        title="Products API",
        version="1.0.0",
        description=(
            "A compact FastAPI reference: register a seller, log in, and manage "
            "products. All product routes require a bearer token; only the owner "
            "can update or delete a product. Prices use integer minor units."
        ),
    )
    # Validate the Host header before routing. HTTPS and rate limits belong at ingress.
    application.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # FastAPI normally echoes invalid inputs. Avoid returning passwords or tokens.
        errors = [{key: error[key] for key in ("loc", "msg", "type")} for error in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errors)})

    @application.exception_handler(SQLAlchemyError)
    async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        # Engine.hide_parameters keeps bound values out of database error logs.
        logger.error("Database operation failed", exc_info=exc)
        return JSONResponse(status_code=503, content={"detail": "Database unavailable"})

    @application.get("/health", tags=["Health"])
    def health(db: DbSession) -> dict[str, str]:
        """Readiness probe: a reachable API alone does not prove the database works."""
        db.execute(text("SELECT 1"))
        return {"status": "ok"}

    # Schema changes belong to Alembic, never import-time create_all().
    # Registering routers exposes their endpoints; importing them alone does not.
    application.include_router(sellers.router)
    application.include_router(auth.router)
    application.include_router(products.router)
    return application


# Uvicorn imports this object via the "app.main:app" module-and-attribute path.
app = create_app()
