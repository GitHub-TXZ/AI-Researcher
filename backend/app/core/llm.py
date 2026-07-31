from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Iterator, Optional


class LLM:
    """OpenAI-compatible chat client using urllib (avoids httpx hang on some endpoints)."""

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 60,
        temperature: float = 0.2,
    ):
        self.model = model or os.getenv("LLM_MODEL_ID") or "gpt-4o-mini"
        self.api_key = api_key or os.getenv("LLM_API_KEY") or ""
        self.base_url = (base_url or os.getenv("LLM_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.timeout = timeout
        self.temperature = temperature

    def _post(self, body: dict[str, Any], stream: bool = False, timeout: int | None = None):
        body = {"model": self.model, "temperature": self.temperature, **body, "stream": stream}
        data = json.dumps(body).encode("utf-8")
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream" if stream else "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        return urllib.request.urlopen(req, timeout=timeout or self.timeout)

    def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        try:
            resp = self._post({"messages": messages, **kwargs}, stream=False)
            data = json.loads(resp.read().decode("utf-8"))
            return (data["choices"][0]["message"]["content"] or "").strip()
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")
            raise RuntimeError(f"LLM HTTP {e.code}: {body[:300]}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"LLM 连接失败: {e.reason}") from e

    def stream(self, messages: list[dict[str, str]], **kwargs: Any) -> Iterator[str]:
        resp = self._post({"messages": messages, **kwargs}, stream=True)
        buf = ""
        for raw in resp:  # iterates over bytes lines
            buf += raw.decode("utf-8", "ignore")
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    return
                try:
                    obj = json.loads(payload)
                    delta = obj["choices"][0].get("delta", {}).get("content")
                    if delta:
                        yield delta
                except Exception:
                    continue
