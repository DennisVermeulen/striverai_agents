"""Batch workflow execution — run one workflow with multiple parameter sets.

Orchestrates sequential execution: loads workflow once, loops through rows,
resolves parameters per row, runs direct/AI replay, broadcasts progress.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field

from local_agent.agent.loop import TaskState, run_agent_loop
from local_agent.agent.replay import run_workflow_direct
from local_agent.agent.workflow import Workflow
from local_agent.api.models import TaskStatus
from local_agent.api.websocket import broadcast
from local_agent.browser.manager import BrowserManager
from local_agent.browser.screenshot import ScreenshotCapture
from local_agent.utils.logging import logger


@dataclass
class BatchRowResult:
    index: int
    parameters: dict[str, str]
    status: str = "pending"  # pending / running / completed / failed / skipped
    task_id: str = ""
    error: str = ""


@dataclass
class BatchState:
    batch_id: str
    workflow_name: str
    mode: str  # "direct" or "ai"
    rows: list[dict[str, str]]
    current_index: int = 0
    results: list[BatchRowResult] = field(default_factory=list)
    status: str = "pending"  # pending / running / completed / failed / cancelled
    _cancel: bool = False

    def cancel(self) -> None:
        self._cancel = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancel

    @property
    def completed_count(self) -> int:
        return sum(1 for r in self.results if r.status == "completed")

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.results if r.status == "failed")


async def run_batch(
    batch: BatchState,
    workflow: Workflow,
    browser: BrowserManager,
    screenshot: ScreenshotCapture,
    tasks: dict[str, TaskState],
) -> None:
    """Run a workflow for each row of parameters sequentially."""
    batch.status = "running"
    await _broadcast_batch(batch)

    for i, row in enumerate(batch.rows):
        if batch.is_cancelled:
            # Mark remaining rows as skipped
            for r in batch.results[i:]:
                r.status = "skipped"
            batch.status = "cancelled"
            await _broadcast_batch(batch)
            logger.info("Batch %s cancelled at row %d", batch.batch_id, i)
            return

        batch.current_index = i
        row_result = batch.results[i]
        row_result.status = "running"
        await _broadcast_batch(batch)

        try:
            # Resolve parameters for this row
            resolved = workflow.resolve(row)

            # Create a task for this row
            task_id = uuid.uuid4().hex[:12]
            instruction = (
                resolved.to_instruction()
                if batch.mode == "ai"
                else f"Batch {batch.workflow_name} [{i + 1}/{len(batch.rows)}]"
            )
            task = TaskState(task_id=task_id, instruction=instruction)
            tasks[task_id] = task
            row_result.task_id = task_id

            # Navigate to start URL
            if resolved.start_url:
                await browser.page.goto(
                    resolved.start_url, wait_until="domcontentloaded"
                )

            # Run the workflow (await — not fire-and-forget)
            if batch.mode == "ai":
                await run_agent_loop(task, browser, screenshot)
            else:
                await run_workflow_direct(task, browser, screenshot, resolved)

            # Check task result
            if task.status == TaskStatus.completed:
                row_result.status = "completed"
            else:
                row_result.status = "failed"
                row_result.error = task.error or "Task did not complete"

        except Exception as exc:
            row_result.status = "failed"
            row_result.error = str(exc)
            logger.error("Batch row %d failed: %s", i, exc)

        await _broadcast_batch(batch)

    batch.status = "completed"
    await _broadcast_batch(batch)
    logger.info(
        "Batch %s finished: %d completed, %d failed",
        batch.batch_id,
        batch.completed_count,
        batch.failed_count,
    )


async def _broadcast_batch(batch: BatchState) -> None:
    current_row = {}
    if 0 <= batch.current_index < len(batch.rows):
        current_row = batch.rows[batch.current_index]

    await broadcast(
        {
            "type": "batch_progress",
            "batch_id": batch.batch_id,
            "workflow_name": batch.workflow_name,
            "status": batch.status,
            "current_index": batch.current_index,
            "total": len(batch.rows),
            "completed": batch.completed_count,
            "failed": batch.failed_count,
            "current_row": current_row,
        }
    )
