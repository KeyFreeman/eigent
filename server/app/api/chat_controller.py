# ========= Copyright 2025-2026 @ Eigent.ai All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0.

import json
from typing import Any, AsyncIterator

import httpx
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.model_controller import _auth_headers, _normalize_openai_base_url

router = APIRouter(tags=["Office Local Chat"])


class OfficeChatRequest(BaseModel):
    project_id: str | None = None
    task_id: str | None = None
    question: str = Field("", description="User request")
    model_platform: str = Field("ollama", description="Model provider")
    model_type: str = Field(..., description="Model name")
    api_key: str | None = None
    api_url: str | None = None
    language: str | None = None
    extra_params: dict[str, Any] | None = None


def _sse(step: str, data: Any) -> str:
    return f"data: {json.dumps({'step': step, 'data': data}, ensure_ascii=False)}\n\n"


def _chunk_text(chunk: dict[str, Any]) -> str:
    choices = chunk.get("choices") or []
    if not choices:
        return ""
    delta = choices[0].get("delta") or {}
    content = delta.get("content")
    if isinstance(content, str):
        return content
    message = choices[0].get("message") or {}
    content = message.get("content")
    return content if isinstance(content, str) else ""


def _ollama_native_chat_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        base = base[: -len("/v1")]
    return f"{base}/api/chat"


def _chat_messages(req: OfficeChatRequest) -> list[dict[str, str]]:
    language = req.language or "zh-Hant"
    question = req.question.strip()
    return [
        {
            "role": "system",
            "content": (
                "You are an AI assistant for a Taiwan architecture office. "
                "Respond in Traditional Chinese unless the user asks otherwise. "
                "Be practical, concise, and provide concrete next steps. "
                "If the request involves Excel, schedules, drawings, Revit, BIM, "
                "or office documents, describe the exact table/file structure you would create."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Language preference: {language}\n"
                f"User task: {question}\n\n"
                "First briefly understand the task, then provide a useful result or execution plan."
            ),
        },
    ]


async def _stream_ollama_native(
    req: OfficeChatRequest,
    messages: list[dict[str, str]],
) -> AsyncIterator[str]:
    base_url = _normalize_openai_base_url(req.api_url, req.model_platform)
    chat_url = _ollama_native_chat_url(base_url)
    payload: dict[str, Any] = {
        "model": req.model_type,
        "messages": messages,
        "stream": True,
        "think": False,
        "options": {"temperature": 0.2, "num_predict": 1600},
    }

    answer = ""
    yield _sse("notice", {"process_task_id": "", "notice": "Calling local Ollama model..."})

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
            async with client.stream("POST", chat_url, json=payload) as response:
                if response.status_code >= 400:
                    body = await response.aread()
                    message = body.decode("utf-8", errors="replace")
                    yield _sse(
                        "error",
                        {
                            "content": (
                                f"Local Ollama request failed: "
                                f"{response.status_code} {message}"
                            )
                        },
                    )
                    yield _sse("end", f"Local Ollama request failed: {response.status_code}")
                    return

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    message = chunk.get("message") or {}
                    text = message.get("content")
                    if not isinstance(text, str) or not text:
                        continue
                    answer += text
                    yield _sse("decompose_text", {"content": text})
    except httpx.HTTPError as exc:
        yield _sse("error", {"content": f"Local Ollama connection failed: {exc}"})
        yield _sse("end", f"Local Ollama connection failed: {exc}")
        return

    yield _sse("end", answer or "The local model returned no visible content.")


async def _stream_openai_compatible(req: OfficeChatRequest) -> AsyncIterator[str]:
    base_url = _normalize_openai_base_url(req.api_url, req.model_platform)
    if not base_url:
        yield _sse(
            "error",
            {
                "content": "Model endpoint URL is missing. Please configure Agents > Models first."
            },
        )
        yield _sse("end", "Model endpoint URL is missing.")
        return

    question = req.question.strip()
    if not question:
        yield _sse("end", "Please enter a task.")
        return

    messages = _chat_messages(req)
    if req.model_platform.lower() == "ollama":
        async for event in _stream_ollama_native(req, messages):
            yield event
        return

    completion_url = f"{base_url}/chat/completions"
    payload: dict[str, Any] = {
        "model": req.model_type,
        "stream": True,
        "temperature": 0.2,
        "max_tokens": 1600,
        "messages": messages,
    }

    answer = ""
    yield _sse("notice", {"process_task_id": "", "notice": "Calling local model..."})

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
            async with client.stream(
                "POST",
                completion_url,
                headers=_auth_headers(req.api_key),
                json=payload,
            ) as response:
                if response.status_code >= 400:
                    body = await response.aread()
                    message = body.decode("utf-8", errors="replace")
                    yield _sse(
                        "error",
                        {
                            "content": (
                                f"Local model request failed: "
                                f"{response.status_code} {message}"
                            )
                        },
                    )
                    yield _sse("end", f"Local model request failed: {response.status_code}")
                    return

                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if not raw or raw == "[DONE]":
                        continue
                    try:
                        chunk = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    text = _chunk_text(chunk)
                    if not text:
                        continue
                    answer += text
                    yield _sse("decompose_text", {"content": text})
    except httpx.HTTPError as exc:
        yield _sse("error", {"content": f"Local model connection failed: {exc}"})
        yield _sse("end", f"Local model connection failed: {exc}")
        return

    yield _sse("end", answer or "The local model returned no visible content.")


@router.post("/chat")
async def office_chat(req: OfficeChatRequest):
    return StreamingResponse(
        _stream_openai_compatible(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
