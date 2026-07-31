from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.llm import LLM
from app.domain import writing
from app.settings import settings
from app.storage.kb import KnowledgeBase

router = APIRouter(prefix="/api/write", tags=["writing"])


def _kb() -> KnowledgeBase:
    return KnowledgeBase(settings.root)


def _llm() -> LLM:
    return LLM(settings.llm_model_id, settings.llm_api_key, settings.llm_base_url, settings.llm_timeout)


class ReviewIn(BaseModel):
    topic: str
    lang: str = "zh"
    style: str = "综述"


class PolishIn(BaseModel):
    draft: str
    focus: str = ""


class TranslateIn(BaseModel):
    text: str
    direction: str = "en2zh"  # en2zh | zh2en


@router.post("/review")
def review(body: ReviewIn):
    try:
        text = writing.write_review(_kb(), _llm(), body.topic, body.lang, body.style)
        return {"ok": True, "text": text}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "text": ""}


@router.post("/polish")
def polish(body: PolishIn):
    try:
        text = writing.polish(_kb(), _llm(), body.draft, body.focus)
        return {"ok": True, "text": text}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "text": ""}


@router.post("/translate")
def translate(body: TranslateIn):
    try:
        text = writing.translate(_kb(), _llm(), body.text, body.direction)
        return {"ok": True, "text": text}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "text": ""}
