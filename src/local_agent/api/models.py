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


class ConfigResponse(BaseModel):
    llm_provider: str
    llm_model: str
    ollama_model: str
    ollama_base_url: str
    agent_max_steps: int
    agent_step_delay: float


class ConfigUpdateRequest(BaseModel):
    llm_provider: str | None = None
    llm_model: str | None = None
    ollama_model: str | None = None
    agent_max_steps: int | None = Field(None, ge=1, le=200)
    agent_step_delay: float | None = Field(None, ge=0, le=10)


# --- Recording / Workflow models ---


class RecordingStopRequest(BaseModel):
    name: str = Field(..., description="Workflow name (used as filename)", min_length=1, max_length=100)
    description: str = Field("", description="Optional description")


class WorkflowStepResponse(BaseModel):
    action: str
    description: str = ""
    coordinates: list[int] | None = None
    text: str = ""
    key: str = ""
    url: str = ""
    element: dict = {}


class WorkflowResponse(BaseModel):
    name: str
    description: str = ""
    start_url: str = ""
    recorded_at: str = ""
    steps: list[WorkflowStepResponse] = []


class WorkflowListResponse(BaseModel):
    workflows: list[WorkflowResponse]
