"""Minimal OpenAI-compatible chat client (works with Ollama, llama.cpp server, vLLM, LM Studio)."""
from __future__ import annotations

import json
import re
from typing import Any, Protocol

import httpx


class LLM(Protocol):
    def chat(self, system: str, user: str, temperature: float = 0.8, max_tokens: int = 1200) -> str: ...


class OpenAICompatClient:
    def __init__(self, base_url: str, model: str, api_key: str = "", timeout_s: float = 300):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.timeout_s = timeout_s

    def chat(self, system: str, user: str, temperature: float = 0.8, max_tokens: int = 1200) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        r = httpx.post(f"{self.base_url}/chat/completions", json=payload, headers=self.headers, timeout=self.timeout_s)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()


def extract_json(text: str) -> Any:
    """Parse the first JSON object/array in an LLM reply, tolerating code fences and chatter."""
    text = re.sub(r"```(?:json)?", "", text)
    for opener, closer in (("[", "]"), ("{", "}")):
        start, end = text.find(opener), text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError("No JSON found in LLM output")
