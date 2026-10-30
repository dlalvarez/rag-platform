"""F00 liveness endpoint. This is not a content or tenant API."""

import os

from fastapi import FastAPI

from rag_platform.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env(os.environ)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings

    @app.get("/healthz")
    def health() -> dict[str, str]:
        # Liveness only; database/object-store availability is tested separately.
        return {"status": "ok", "phase": "F00"}

    return app


app = create_app()
