import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from local_agent.agent.actions import ActionExecutor
from local_agent.agent.prompts import SYSTEM_PROMPT
from local_agent.api.models import TaskStatus
from local_agent.api.websocket import broadcast
from local_agent.browser.manager import BrowserManager
from local_agent.browser.screenshot import ScreenshotCapture
from local_agent.config import settings
from local_agent.llm.base import LLMProvider
from local_agent.llm.factory import create_llm_provider
from local_agent.utils.logging import logger


@dataclass
class TaskState:
    """Tracks the state of a running agent task."""

    task_id: str
    instruction: str
    status: TaskStatus = TaskStatus.pending
    steps_completed: int = 0
    current_action: str | None = None
    result: str | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    _cancel: bool = False

    def cancel(self) -> None:
        self._cancel = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancel


async def run_agent_loop(
    task: TaskState,
    browser: BrowserManager,
    screenshot: ScreenshotCapture,
) -> None:
    """Core agent loop: screenshot → LLM → action → repeat."""
    llm = create_llm_provider(screenshot.scaled_width, screenshot.scaled_height)
    executor = ActionExecutor(browser.page, screenshot)

    max_steps = settings.agent_max_steps
    task.status = TaskStatus.running

    await _broadcast_status(task)

    # Navigate to URL if provided (from instruction metadata)
    # Build initial message with a screenshot
    messages: list[dict] = []

    # Take initial screenshot
    b64 = await screenshot.capture(browser.page, save=True)
    messages.append(
        {
            "role": "user",
            "content": [
                {"type": "text", "text": task.instruction},
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": b64,
                    },
                },
            ],
        }
    )

    recent_actions: list[str] = []

    for step in range(max_steps):
        if task.is_cancelled:
            task.status = TaskStatus.cancelled
            task.result = f"Cancelled after {step} steps"
            await _broadcast_status(task)
            return

        logger.info("Step %d/%d", step + 1, max_steps)

        # Send to LLM
        try:
            response = await llm.send(messages, system=SYSTEM_PROMPT)
        except Exception as exc:
            task.status = TaskStatus.failed
            task.error = f"LLM error: {exc}"
            await _broadcast_status(task)
            return

        # Append assistant response to conversation
        messages.append({"role": "assistant", "content": response.raw_content})

        # If no actions, the task is done
        if not response.has_actions:
            task.status = TaskStatus.completed
            task.result = response.text or "Task completed"
            task.steps_completed = step + 1
            await _broadcast_status(task)
            logger.info("Task completed: %s", task.result[:100])
            return

        # Execute each action and collect tool results
        tool_results: list[dict] = []

        for action in response.actions:
            task.current_action = f"{action.action}"
            task.steps_completed = step + 1
            await _broadcast_status(task)

            if action.action == "screenshot":
                # Just take a screenshot, don't execute anything
                b64 = await screenshot.capture(browser.page, save=True)
                tool_results.append(llm.build_screenshot_result(action.tool_use_id, b64))
                continue

            # Check for loop detection
            action_sig = f"{action.action}:{action.coordinate}:{action.text}"
            recent_actions.append(action_sig)
            if len(recent_actions) > 6:
                recent_actions.pop(0)
            if _is_stuck(recent_actions):
                logger.warning("Loop detected — sending error to LLM")
                tool_results.append(
                    llm.build_error_result(
                        action.tool_use_id,
                        "You appear to be stuck repeating the same action. "
                        "Try a completely different approach.",
                    )
                )
                continue

            # Execute the action
            error = await executor.execute(action)
            await asyncio.sleep(settings.agent_step_delay)

            # Take a screenshot after the action
            b64 = await screenshot.capture(browser.page, save=True)

            if error:
                tool_results.append(llm.build_error_result(action.tool_use_id, error))
            else:
                tool_results.append(llm.build_screenshot_result(action.tool_use_id, b64))

        # Append tool results as a user message
        messages.append({"role": "user", "content": tool_results})

    # Max steps reached
    task.status = TaskStatus.failed
    task.error = f"Max steps ({max_steps}) reached without completing the task"
    await _broadcast_status(task)


def _is_stuck(recent: list[str]) -> bool:
    """Detect if the last 4+ actions are identical."""
    if len(recent) < 4:
        return False
    return len(set(recent[-4:])) == 1


async def _broadcast_status(task: TaskState) -> None:
    await broadcast(
        {
            "type": "task_status",
            "task_id": task.task_id,
            "status": task.status.value,
            "steps_completed": task.steps_completed,
            "current_action": task.current_action,
            "result": task.result,
            "error": task.error,
        }
    )
