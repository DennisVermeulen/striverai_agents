import asyncio
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import Response

from local_agent.agent.loop import TaskState, run_agent_loop
from local_agent.agent.replay import run_workflow_direct
from local_agent.agent.workflow import Workflow, process_raw_events
from local_agent.api.models import (
    ConfigResponse,
    ConfigUpdateRequest,
    HealthResponse,
    NavigateRequest,
    RecordingStopRequest,
    TaskRequest,
    TaskResponse,
    TaskStatus,
    TaskStatusResponse,
    WorkflowListResponse,
    WorkflowResponse,
    WorkflowStepResponse,
)
from local_agent.browser.manager import BrowserManager
from local_agent.browser.recorder import BrowserRecorder
from local_agent.browser.screenshot import ScreenshotCapture
from local_agent.browser.session import save_session
from local_agent.config import settings

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


@router.get("/config", response_model=ConfigResponse)
async def get_config() -> ConfigResponse:
    return ConfigResponse(
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model,
        ollama_model=settings.ollama_model,
        ollama_base_url=settings.ollama_base_url,
        agent_max_steps=settings.agent_max_steps,
        agent_step_delay=settings.agent_step_delay,
    )


@router.post("/config", response_model=ConfigResponse)
async def update_config(body: ConfigUpdateRequest) -> ConfigResponse:
    if body.llm_provider is not None:
        settings.llm_provider = body.llm_provider
    if body.llm_model is not None:
        settings.llm_model = body.llm_model
    if body.ollama_model is not None:
        settings.ollama_model = body.ollama_model
    if body.agent_max_steps is not None:
        settings.agent_max_steps = body.agent_max_steps
    if body.agent_step_delay is not None:
        settings.agent_step_delay = body.agent_step_delay
    return ConfigResponse(
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model,
        ollama_model=settings.ollama_model,
        ollama_base_url=settings.ollama_base_url,
        agent_max_steps=settings.agent_max_steps,
        agent_step_delay=settings.agent_step_delay,
    )


# --- Recording endpoints ---


@router.post("/recording/start")
async def recording_start(request: Request) -> dict:
    if request.app.state.recorder and request.app.state.recorder.is_recording:
        raise HTTPException(status_code=409, detail="Already recording")

    bm = _browser(request)
    recorder = BrowserRecorder(bm.page)
    await recorder.start()
    request.app.state.recorder = recorder
    return {"status": "ok", "message": "Recording started"}


@router.post("/recording/stop")
async def recording_stop(request: Request, body: RecordingStopRequest) -> WorkflowResponse:
    recorder: BrowserRecorder | None = request.app.state.recorder
    if not recorder or not recorder.is_recording:
        raise HTTPException(status_code=409, detail="Not recording")

    bm = _browser(request)
    raw_events = await recorder.stop()
    request.app.state.recorder = None

    # Process raw events into clean workflow steps
    start_url = bm.page.url
    steps = process_raw_events(raw_events, start_url=start_url)

    # Create and save workflow
    workflow = Workflow(
        name=body.name,
        description=body.description,
        start_url=start_url,
        steps=steps,
    )
    workflow.save()

    return _workflow_to_response(workflow)


# --- Workflow endpoints ---


@router.get("/workflows", response_model=WorkflowListResponse)
async def list_workflows() -> WorkflowListResponse:
    workflows = Workflow.list_all()
    return WorkflowListResponse(
        workflows=[_workflow_to_response(w) for w in workflows]
    )


@router.get("/workflows/{name}", response_model=WorkflowResponse)
async def get_workflow(name: str) -> WorkflowResponse:
    try:
        workflow = Workflow.load(name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Workflow '{name}' not found")
    return _workflow_to_response(workflow)


@router.get("/workflows/{name}/preview")
async def preview_workflow(name: str) -> dict:
    """Preview the AI instruction that would be generated for a workflow."""
    try:
        workflow = Workflow.load(name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Workflow '{name}' not found")
    return {
        "name": workflow.name,
        "instruction": workflow.to_instruction(),
        "step_count": len(workflow.steps),
    }


@router.post("/workflows/{name}/run", response_model=TaskResponse)
async def run_workflow(request: Request, name: str, mode: str = "direct") -> TaskResponse:
    """Run a workflow. mode=direct (default, free) or mode=ai (uses LLM)."""
    try:
        workflow = Workflow.load(name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Workflow '{name}' not found")

    tasks = _tasks(request)

    # Only one task at a time
    running = [t for t in tasks.values() if t.status == TaskStatus.running]
    if running:
        raise HTTPException(status_code=409, detail="A task is already running")

    instruction = workflow.to_instruction() if mode == "ai" else f"Replay workflow: {workflow.name}"
    task_id = uuid.uuid4().hex[:12]
    task = TaskState(task_id=task_id, instruction=instruction)
    tasks[task_id] = task

    bm = _browser(request)
    sc = _screenshot(request)

    # Navigate to start URL if present
    if workflow.start_url:
        await bm.page.goto(workflow.start_url, wait_until="domcontentloaded")

    if mode == "ai":
        # AI-based replay: uses LLM to interpret screenshots (costs API credits)
        asyncio.create_task(run_agent_loop(task, bm, sc))
    else:
        # Direct replay: Playwright locators + coordinates (free, fast)
        asyncio.create_task(run_workflow_direct(task, bm, sc, workflow))

    return TaskResponse(
        task_id=task_id,
        status=task.status,
        instruction=instruction,
    )


@router.delete("/workflows/{name}")
async def delete_workflow(name: str) -> dict:
    deleted = Workflow.delete(name)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Workflow '{name}' not found")
    return {"status": "ok", "name": name}


def _workflow_to_response(workflow: Workflow) -> WorkflowResponse:
    return WorkflowResponse(
        name=workflow.name,
        description=workflow.description,
        start_url=workflow.start_url,
        recorded_at=workflow.recorded_at,
        steps=[
            WorkflowStepResponse(
                action=s.action,
                description=s.description,
                coordinates=s.coordinates,
                text=s.text,
                key=s.key,
                url=s.url,
                element=s.element.to_dict(),
            )
            for s in workflow.steps
        ],
    )
