# ========= Copyright 2025-2026 @ Eigent.ai All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0.

from typing import Any
from urllib.parse import urlparse, urlunparse

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(tags=["Model Validation"])


class ValidateModelRequest(BaseModel):
    model_platform: str = Field("ollama", description="Model platform")
    model_type: str = Field(..., description="Model type")
    api_key: str | None = Field(None, description="API key")
    url: str | None = Field(None, description="OpenAI-compatible base URL")
    model_config_dict: dict[str, Any] | None = None
    extra_params: dict[str, Any] | None = None
    include_diagnostics: bool = False


class ValidateModelResponse(BaseModel):
    is_valid: bool
    is_tool_calls: bool
    error_code: str | None = None
    error: dict[str, Any] | None = None
    message: str
    error_type: str | None = None
    failed_stage: str | None = None
    successful_stages: list[str] | None = None
    diagnostic_info: dict[str, Any] | None = None
    model_response_info: dict[str, Any] | None = None
    tool_call_info: dict[str, Any] | None = None
    validation_stages: dict[str, bool] | None = None


def _normalize_openai_base_url(url: str | None, platform: str) -> str:
    if url and url.strip():
        base_url = url.strip().rstrip("/")
    elif platform.lower() == "ollama":
        base_url = "http://host.docker.internal:11434/v1"
    else:
        base_url = ""

    if not base_url:
        return base_url

    if base_url.endswith("/chat/completions"):
        base_url = base_url[: -len("/chat/completions")]
    elif base_url.endswith("/completions"):
        base_url = base_url[: -len("/completions")]

    return base_url.rstrip("/")


def _host_docker_internal_url(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.hostname not in {"localhost", "127.0.0.1"}:
        return None

    netloc = "host.docker.internal"
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"

    return urlunparse(parsed._replace(netloc=netloc))


def _auth_headers(api_key: str | None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key and api_key not in {"not-required", "ollama", "none"}:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


async def _try_validate_once(
    base_url: str,
    request: ValidateModelRequest,
) -> tuple[dict[str, Any] | None, str | None]:
    completion_url = f"{base_url}/chat/completions"
    payload = {
        "model": request.model_type,
        "messages": [
            {
                "role": "system",
                "content": "You must call the provided tool. Do not answer in natural language.",
            },
            {
                "role": "user",
                "content": "Call office_ping with ok set to true.",
            }
        ],
        "stream": False,
        "temperature": 0,
        "max_tokens": 64,
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "office_ping",
                    "description": "Return whether the local model validation reached the tool system.",
                    "parameters": {
                        "type": "object",
                        "properties": {"ok": {"type": "boolean"}},
                        "required": ["ok"],
                    },
                },
            }
        ],
        "tool_choice": "required",
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
            response = await client.post(
                completion_url,
                headers=_auth_headers(request.api_key),
                json=payload,
            )
    except httpx.HTTPError as exc:
        return None, str(exc)

    if response.status_code >= 400:
        try:
            body = response.json()
        except ValueError:
            body = response.text
        return None, f"{response.status_code} {body}"

    try:
        data = response.json()
    except ValueError as exc:
        return None, f"Invalid JSON response: {exc}"

    return data, None


def _tool_calls_from_response(data: dict[str, Any]) -> list[Any]:
    choices = data.get("choices") or []
    if not choices:
        return []
    message = choices[0].get("message") or {}
    return message.get("tool_calls") or []


@router.post("/model/validate", response_model=ValidateModelResponse)
async def validate_model(request: ValidateModelRequest):
    base_url = _normalize_openai_base_url(request.url, request.model_platform)
    if not base_url:
        return ValidateModelResponse(
            is_valid=False,
            is_tool_calls=False,
            error_code="missing_endpoint_url",
            error_type="configuration_error",
            failed_stage="initialization",
            message="Model endpoint URL is required.",
            validation_stages={"initialization": False},
        )

    candidate_urls = [base_url]
    docker_host_url = _host_docker_internal_url(base_url)
    if docker_host_url and docker_host_url not in candidate_urls:
        candidate_urls.append(docker_host_url)

    errors: list[str] = []
    successful_url: str | None = None
    data: dict[str, Any] | None = None

    for candidate_url in candidate_urls:
        data, error = await _try_validate_once(candidate_url, request)
        if data is not None:
            successful_url = candidate_url
            break
        errors.append(f"{candidate_url}: {error}")

    if data is None:
        return ValidateModelResponse(
            is_valid=False,
            is_tool_calls=False,
            error_code="model_connection_failed",
            error_type="network_error",
            failed_stage="model_call",
            message="; ".join(errors) or "Model validation failed.",
            validation_stages={"initialization": True, "model_call": False},
            diagnostic_info={"attempted_urls": candidate_urls}
            if request.include_diagnostics
            else None,
        )

    tool_calls = _tool_calls_from_response(data)
    if tool_calls:
        return ValidateModelResponse(
            is_valid=True,
            is_tool_calls=True,
            message="Validation successful. Model supports tool calling.",
            successful_stages=["initialization", "model_call", "tool_call"],
            validation_stages={
                "initialization": True,
                "model_call": True,
                "tool_call": True,
            },
            diagnostic_info={"validated_url": successful_url}
            if request.include_diagnostics
            else None,
            model_response_info={"id": data.get("id"), "model": data.get("model")}
            if request.include_diagnostics
            else None,
            tool_call_info={"count": len(tool_calls)}
            if request.include_diagnostics
            else None,
        )

    return ValidateModelResponse(
        is_valid=True,
        is_tool_calls=False,
        error_code="tool_call_not_supported",
        error_type="tool_call_not_supported",
        failed_stage="tool_call",
        message=(
            "Model call succeeded, but this model did not return a tool call. "
            "Eigent requires a model with function/tool calling support."
        ),
        successful_stages=["initialization", "model_call"],
        validation_stages={
            "initialization": True,
            "model_call": True,
            "tool_call": False,
        },
        diagnostic_info={"validated_url": successful_url}
        if request.include_diagnostics
        else None,
        model_response_info={"id": data.get("id"), "model": data.get("model")}
        if request.include_diagnostics
        else None,
    )
