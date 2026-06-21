import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import auth, datasets, documents, graph, meta, search, stats
from core.config import settings
from storage.neo4j_client import close_driver, ensure_schema
from storage.postgres import init_db
from storage.qdrant_client import ensure_collection

logging.basicConfig(level=settings.app_log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting knowledge-service (%s)", settings.app_env)
    await init_db()
    await ensure_collection()
    await ensure_schema()
    yield
    await close_driver()
    logger.info("stopped")


app = FastAPI(
    title="Knowledge Service",
    description="Knowledge base + Knowledge graph service for OpenClaw integration",
    version="0.5.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_dev else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(datasets.router)
app.include_router(documents.router)
app.include_router(search.router)
app.include_router(graph.router)
app.include_router(stats.router)
app.include_router(meta.router)


@app.get("/", tags=["meta"])
async def root():
    return {"name": "knowledge-service", "version": "0.5.0", "docs": "/docs"}


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok", "env": settings.app_env}
