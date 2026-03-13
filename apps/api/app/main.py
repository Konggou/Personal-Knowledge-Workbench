from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.database import initialize_database
from app.core.settings import get_settings
from app.services.vector_store import VectorStore


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    try:
        VectorStore().ensure_collection()
    except Exception:
        pass
    yield


settings = get_settings()

app = FastAPI(
    title="Personal Knowledge Workbench API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
    allow_origin_regex=r"https?://(127\.0\.0\.1|localhost):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)
