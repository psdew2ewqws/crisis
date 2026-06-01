from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import router
from app.api.ws.router import router as ws_router
from app.voc.router import router as voc_router
from app.repositories.factory import get_repos
from app.core.database import dispose_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load repos
    app.state.repos = get_repos()
    yield
    # Shutdown: cleanup DB pool
    await dispose_engine()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Crisis-Solving Brain API",
        version="0.1.0",
        description="National Crisis Management Simulation Engine",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    app.include_router(ws_router)
    app.include_router(voc_router, prefix="/api/v1")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
