"""Direct workflow replay via Playwright — no AI needed.

Executes recorded workflow steps using Playwright locators (aria_label, role,
text, placeholder) with coordinate fallback. Cost: $0, speed: seconds.
"""

from __future__ import annotations

import asyncio

from playwright.async_api import Page

from local_agent.agent.loop import TaskState, _broadcast_status
from local_agent.agent.workflow import Workflow, WorkflowStep, ElementInfo
from local_agent.api.models import TaskStatus
from local_agent.browser.manager import BrowserManager
from local_agent.browser.screenshot import ScreenshotCapture
from local_agent.utils.logging import logger


async def run_workflow_direct(
    task: TaskState,
    browser: BrowserManager,
    screenshot: ScreenshotCapture,
    workflow: Workflow,
) -> None:
    """Execute workflow steps directly via Playwright — no AI, no cost."""
    page = browser.page
    task.status = TaskStatus.running
    await _broadcast_status(task)

    for i, step in enumerate(workflow.steps):
        if task.is_cancelled:
            task.status = TaskStatus.cancelled
            task.result = f"Cancelled after {i} steps"
            await _broadcast_status(task)
            return

        task.current_action = step.description or step.action
        task.steps_completed = i + 1
        await _broadcast_status(task)
        logger.info("Replay step %d/%d: %s", i + 1, len(workflow.steps), step.description)

        error = await _execute_step(page, step)
        if error:
            task.status = TaskStatus.failed
            task.error = f"Step {i + 1} failed: {error}"
            await _broadcast_status(task)
            logger.error("Replay failed at step %d: %s", i + 1, error)
            return

        # Wait for page to settle after action
        await asyncio.sleep(0.8)

        # Take screenshot for WebSocket progress
        await screenshot.capture(page, save=True)

    task.status = TaskStatus.completed
    task.result = f"Workflow completed ({len(workflow.steps)} steps)"
    task.steps_completed = len(workflow.steps)
    await _broadcast_status(task)
    logger.info("Workflow '%s' completed successfully", workflow.name)


async def _execute_step(page: Page, step: WorkflowStep) -> str | None:
    """Execute a single workflow step. Returns error string or None on success."""
    try:
        if step.action == "click":
            return await _do_click(page, step)
        elif step.action == "type":
            return await _do_type(page, step)
        elif step.action == "key":
            return await _do_key(page, step)
        elif step.action == "navigate":
            await page.goto(step.url, wait_until="domcontentloaded")
            return None
        else:
            return f"Unknown action: {step.action}"
    except Exception as e:
        return str(e)


async def _do_click(page: Page, step: WorkflowStep) -> str | None:
    """Click element by locator, fall back to coordinates."""
    locator = _find_element(page, step.element)
    if locator:
        try:
            await locator.click(timeout=5000)
            return None
        except Exception as e:
            logger.debug("Locator click failed, trying coordinates: %s", e)

    if step.coordinates:
        await page.mouse.click(step.coordinates[0], step.coordinates[1])
        return None

    return "Could not find element and no coordinates available"


async def _do_type(page: Page, step: WorkflowStep) -> str | None:
    """Type text into a field by locator, fall back to coordinates."""
    locator = _find_element(page, step.element)
    if locator:
        try:
            await locator.click(timeout=5000)
            if step.element.contenteditable:
                # For contenteditable divs, use keyboard.type
                await page.keyboard.type(step.text)
            else:
                # For regular inputs, fill is more reliable (clears first)
                await locator.fill(step.text)
            return None
        except Exception as e:
            logger.debug("Locator type failed, trying coordinates: %s", e)

    # Fall back to click coordinates + keyboard type
    if step.coordinates:
        await page.mouse.click(step.coordinates[0], step.coordinates[1])
        await asyncio.sleep(0.2)
        await page.keyboard.type(step.text)
        return None

    # Last resort: just type (assumes field is already focused)
    await page.keyboard.type(step.text)
    return None


async def _do_key(page: Page, step: WorkflowStep) -> str | None:
    """Press a key."""
    key = _normalize_key(step.key)
    await page.keyboard.press(key)
    return None


def _find_element(page: Page, el: ElementInfo):
    """Try to find an element using Playwright locators. Returns locator or None."""
    if not el.tag and not el.aria_label and not el.text and not el.role:
        return None

    # Strategy 1: role + name (most reliable for buttons, links, etc.)
    if el.role and (el.aria_label or el.text):
        name = el.aria_label or el.text
        try:
            return page.get_by_role(el.role, name=name)
        except Exception:
            pass

    # Strategy 2: aria-label directly
    if el.aria_label:
        return page.get_by_label(el.aria_label)

    # Strategy 3: placeholder (for inputs)
    if el.placeholder:
        return page.get_by_placeholder(el.placeholder)

    # Strategy 4: role + text for buttons/links without aria-label
    if el.text and el.role:
        try:
            return page.get_by_role(el.role, name=el.text)
        except Exception:
            pass

    # Strategy 5: exact text match
    if el.text:
        return page.get_by_text(el.text, exact=True)

    return None


def _normalize_key(key: str) -> str:
    """Normalize key names for Playwright."""
    mapping = {
        "enter": "Enter",
        "tab": "Tab",
        "escape": "Escape",
        "backspace": "Backspace",
        "delete": "Delete",
        "space": " ",
    }
    return mapping.get(key.lower(), key)
