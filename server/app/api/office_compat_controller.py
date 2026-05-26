# ========= Copyright 2025-2026 @ Eigent.ai All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0.

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(tags=["Office Compatibility"])

_project_tasks: dict[str, list[dict[str, Any]]] = {}
_project_control: dict[str, dict[str, Any]] = {}
_project_agents: dict[str, list[dict[str, Any]]] = {}


class TaskUpdateRequest(BaseModel):
    task: list[dict[str, Any]] = Field(default_factory=list)


class TakeControlRequest(BaseModel):
    isTakeControl: bool | None = None
    value: bool | None = None
    task_id: str | None = None


class AddAgentRequest(BaseModel):
    agent: dict[str, Any] | None = None
    worker: dict[str, Any] | None = None
    name: str | None = None
    description: str | None = None
    tools: Any | None = None
    mcp_tools: Any | None = None


class HumanReplyRequest(BaseModel):
    content: str | None = None
    answer: str | None = None
    message: str | None = None


@router.put("/task/{project_id}")
async def update_project_tasks(project_id: str, req: TaskUpdateRequest):
    _project_tasks[project_id] = req.task
    return {
        "success": True,
        "project_id": project_id,
        "task_count": len(req.task),
    }


@router.post("/task/{project_id}/start")
async def start_project_tasks(project_id: str):
    tasks = _project_tasks.get(project_id, [])
    return {
        "success": True,
        "project_id": project_id,
        "task_count": len(tasks),
        "message": (
            "Office local mode accepted the task start request. "
            "The current deployment streams local LLM responses through /chat; "
            "full multi-agent tool execution is not enabled yet."
        ),
    }


@router.put("/task/{project_id}/take-control")
async def set_take_control(project_id: str, req: TakeControlRequest):
    value = req.isTakeControl if req.isTakeControl is not None else req.value
    _project_control[project_id] = {
        "isTakeControl": bool(value),
        "task_id": req.task_id,
    }
    return {"success": True, "project_id": project_id, **_project_control[project_id]}


@router.post("/task/{project_id}/add-agent")
async def add_project_agent(project_id: str, req: AddAgentRequest):
    agent = req.agent or req.worker or req.model_dump(exclude_none=True)
    _project_agents.setdefault(project_id, []).append(agent)
    return {
        "success": True,
        "project_id": project_id,
        "agent_count": len(_project_agents[project_id]),
    }


@router.delete("/chat/{project_id}")
async def delete_project_runtime(project_id: str):
    _project_tasks.pop(project_id, None)
    _project_control.pop(project_id, None)
    _project_agents.pop(project_id, None)
    return {"success": True, "project_id": project_id}


@router.post("/chat/{project_id}")
async def improve_project_task(project_id: str, payload: dict[str, Any] | None = None):
    return {
        "success": True,
        "project_id": project_id,
        "message": "Office local mode accepted the improve request.",
        "payload": payload or {},
    }


@router.post("/chat/{project_id}/human-reply")
async def submit_human_reply(project_id: str, req: HumanReplyRequest):
    return {
        "success": True,
        "project_id": project_id,
        "reply": req.content or req.answer or req.message or "",
    }


@router.post("/chat/{project_id}/skip-task")
async def skip_project_task(project_id: str, payload: dict[str, Any] | None = None):
    return {
        "success": True,
        "project_id": project_id,
        "message": "Office local mode accepted the skip-task request.",
        "payload": payload or {},
    }
