from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.llm import LLM
from app.domain import ideation
from app.settings import settings
from app.storage.kb import KnowledgeBase

router = APIRouter(prefix="/api/ideation", tags=["ideation"])


def _kb() -> KnowledgeBase:
    return KnowledgeBase(settings.root)


def _llm() -> LLM:
    return LLM(settings.llm_model_id, settings.llm_api_key, settings.llm_base_url, settings.llm_timeout)


class IdeationIn(BaseModel):
    topic: str = ""
    seed_idea: str = ""
    n_ideas: int = 3
    rounds: int = 2


@router.post("/debate")
def debate(body: IdeationIn):
    def gen():
        try:
            for evt in ideation.run_debate(_kb(), _llm(), body.topic, body.n_ideas, body.rounds, body.seed_idea):
                yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
        except Exception as exc:  # noqa: BLE001
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
