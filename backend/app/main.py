from __future__ import annotations

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from app.api.assets import router as assets_router
from app.api.chat import router as chat_router
from app.api.kb import router as kb_router
from app.api.meta import router as meta_router
from app.api.ideation import router as ideation_router
from app.api.zotero import router as zotero_router
from app.api.write import router as write_router
from app.settings import settings

app = FastAPI(title="PoseLab API", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()] or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(meta_router)
app.include_router(assets_router)
app.include_router(kb_router)
app.include_router(chat_router)
app.include_router(zotero_router)
app.include_router(write_router)
app.include_router(ideation_router)
