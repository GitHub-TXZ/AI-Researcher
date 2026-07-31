from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.llm import LLM
from app.crew.orchestrator import ResearchCrew
from app.settings import settings
from app.storage.assets import AssetStore
from app.storage.kb import KnowledgeBase
from app.tools.factory import build_tools

router = APIRouter(prefix="/api", tags=["chat"])


class ChatIn(BaseModel):
    message: str
    mention: list[str] = Field(default_factory=list)
    history: list[dict] = Field(default_factory=list)  # [{role:"user"|"assistant", content:str}]


def _crew() -> ResearchCrew:
    llm = LLM(settings.llm_model_id, settings.llm_api_key, settings.llm_base_url, settings.llm_timeout)
    assets = AssetStore(settings.root)
    return ResearchCrew(llm, assets, build_tools(assets, KnowledgeBase(settings.root), llm))


@router.post("/chat")
def chat(body: ChatIn):
    crew = _crew()

    def gen():
        try:
            for evt in crew.run_stream(body.message, body.mention or None, body.history or None):
                yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
        except Exception as exc:  # noqa: BLE001
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
