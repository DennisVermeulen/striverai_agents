import asyncio
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import Response

from local_agent.agent.loop import TaskState, run_agent_loop
from local_agent.api.models import (
    HealthResponse,
    NavigateRequest,
    TaskRequest,
    TaskResponse,
    TaskStatus,
    TaskStatusResponse,
)
from local_agent.browser.manager import BrowserManager
from local_agent.browser.screenshot import ScreenshotCapture
from local_agent.browser.session import save_session

router = APIRouter()


def _browser(request: Request) -> BrowserManager:
    return request.app.state.browser


def _screenshot(request: Request) -> ScreenshotCapture:
    return request.app.state.screenshot


def _tasks(request: Request) -> dict[str, TaskState]:
    return request.app.state.tasks


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    bm = _browser(request)
    return HealthResponse(status="ok", browser_ready=bm._page is not None)


@router.get("/screenshot")
async def screenshot(request: Request) -> Response:
    bm = _browser(request)
    sc = _screenshot(request)
    png_bytes = await sc.capture_bytes(bm.page)
    return Response(content=png_bytes, media_type="image/png")


@router.post("/navigate")
async def navigate(request: Request, body: NavigateRequest) -> dict:
    bm = _browser(request)
    await bm.page.goto(body.url, wait_until="domcontentloaded")
    return {"status": "ok", "url": body.url}


@router.post("/session/save")
async def session_save(request: Request) -> dict:
    bm = _browser(request)
    path = await save_session(bm.context)
    return {"status": "ok", "path": str(path)}


@router.post("/task", response_model=TaskResponse)
async def create_task(request: Request, body: TaskRequest) -> TaskResponse:
    tasks = _tasks(request)

    # Only one task at a time
    running = [t for t in tasks.values() if t.status == TaskStatus.running]
    if running:
        raise HTTPException(status_code=409, detail="A task is already running")

    task_id = uuid.uuid4().hex[:12]
    task = TaskState(task_id=task_id, instruction=body.instruction)
    tasks[task_id] = task

    bm = _browser(request)
    sc = _screenshot(request)

    # Navigate first if URL provided
    if body.url:
        await bm.page.goto(body.url, wait_until="domcontentloaded")

    if body.max_steps:
        from local_agent.config import settings

        settings.agent_max_steps = body.max_steps

    # Run the agent loop in the background
    asyncio.create_task(run_agent_loop(task, bm, sc))

    return TaskResponse(
        task_id=task_id,
        status=task.status,
        instruction=body.instruction,
    )


@router.get("/task/{task_id}", response_model=TaskStatusResponse)
async def get_task(request: Request, task_id: str) -> TaskStatusResponse:
    tasks = _tasks(request)
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskStatusResponse(
        task_id=task.task_id,
        status=task.status,
        instruction=task.instruction,
        steps_completed=task.steps_completed,
        current_action=task.current_action,
        result=task.result,
        error=task.error,
    )


@router.post("/task/{task_id}/cancel")
async def cancel_task(request: Request, task_id: str) -> dict:
    tasks = _tasks(request)
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.cancel()
    return {"status": "ok", "task_id": task_id}
