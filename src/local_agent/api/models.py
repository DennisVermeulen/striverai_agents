from enum import Enum

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class TaskRequest(BaseModel):
    instruction: str = Field(..., description="What the agent should do", min_length=1)
    url: str | None = Field(None, description="Optional URL to navigate to first")
    max_steps: int | None = Field(None, ge=1, le=200, description="Override max steps")


class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    instruction: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: TaskStatus
    instruction: str
    steps_completed: int = 0
    current_action: str | None = None
    result: str | None = None
    error: str | None = None


class NavigateRequest(BaseModel):
    url: str = Field(..., description="URL to navigate to")


class HealthResponse(BaseModel):
    status: str = "ok"
    browser_ready: bool = False
