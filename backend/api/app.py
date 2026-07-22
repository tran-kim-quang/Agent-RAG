import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.dependencies import auth_service, database
from backend.api.routers import admin, auth, chat, documents, graph, system
from backend.src.infrastructure.checkpoints import initialize_checkpointer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    auth_service.validate_runtime_config()
    if os.getenv("AUTO_CREATE_SCHEMA", "true").lower() == "true": database.create_schema()
    initialize_checkpointer()
    auth_service.ensure_bootstrap_admin()
    yield


app = FastAPI(title="Agent-RAG API", version="0.2.0", lifespan=lifespan)
origins = [value.strip() for value in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if value.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
for router in (system.router, auth.router, chat.router, documents.router, graph.router, admin.router):
    app.include_router(router)
