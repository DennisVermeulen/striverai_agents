import asyncio

from playwright.async_api import Page

from local_agent.browser.screenshot import ScreenshotCapture
from local_agent.llm.base import AgentAction
from local_agent.utils.errors import BrowserError
from local_agent.utils.logging import logger


class ActionExecutor:
    """Translates AgentAction objects into Playwright calls."""

    def __init__(self, page: Page, screenshot: ScreenshotCapture) -> None:
        self._page = page
        self._screenshot = screenshot

    async def execute(self, action: AgentAction) -> str | None:
        """Execute a single action. Returns an error string or None on success."""
        name = action.action
        logger.info("Executing: %s %s", name, _summarize(action))

        try:
            handler = getattr(self, f"_do_{name}", None)
            if handler is None:
                return f"Unknown action: {name}"
            await handler(action)
            return None
        except Exception as exc:
            logger.warning("Action %s failed: %s", name, exc)
            return f"Action {name} failed: {exc}"

    # -- Action handlers -------------------------------------------------------

    async def _do_screenshot(self, action: AgentAction) -> None:
        pass  # screenshot is always taken after each action in the loop

    async def _do_left_click(self, action: AgentAction) -> None:
        x, y = self._screen_coords(action)
        await self._page.mouse.click(x, y)

    async def _do_right_click(self, action: AgentAction) -> None:
        x, y = self._screen_coords(action)
        await self._page.mouse.click(x, y, button="right")

    async def _do_middle_click(self, action: AgentAction) -> None:
        x, y = self._screen_coords(action)
        await self._page.mouse.click(x, y, button="middle")

    async def _do_double_click(self, action: AgentAction) -> None:
        x, y = self._screen_coords(action)
        await self._page.mouse.dblclick(x, y)

    async def _do_triple_click(self, action: AgentAction) -> None:
        x, y = self._screen_coords(action)
        await self._page.mouse.click(x, y, click_count=3)

    async def _do_mouse_move(self, action: AgentAction) -> None:
        x, y = self._screen_coords(action)
        await self._page.mouse.move(x, y)

    async def _do_left_click_drag(self, action: AgentAction) -> None:
        start = action.raw.get("start_coordinate", action.coordinate)
        end = action.coordinate
        if not start or not end:
            return
        sx, sy = self._screenshot.scale_coordinates_to_screen(*start)
        ex, ey = self._screenshot.scale_coordinates_to_screen(*end)
        await self._page.mouse.move(sx, sy)
        await self._page.mouse.down()
        await self._page.mouse.move(ex, ey)
        await self._page.mouse.up()

    async def _do_type(self, action: AgentAction) -> None:
        if action.text:
            await self._page.keyboard.type(action.text)

    async def _do_key(self, action: AgentAction) -> None:
        if action.text:
            # Anthropic uses "ctrl+a" style, Playwright uses "Control+a"
            combo = _normalize_key_combo(action.text)
            await self._page.keyboard.press(combo)

    async def _do_scroll(self, action: AgentAction) -> None:
        x, y = self._screen_coords(action)
        direction = action.scroll_direction or "down"
        amount = (action.scroll_amount or 3) * 100  # pixels per scroll unit

        dx, dy = 0, 0
        if direction == "down":
            dy = amount
        elif direction == "up":
            dy = -amount
        elif direction == "right":
            dx = amount
        elif direction == "left":
            dx = -amount

        await self._page.mouse.move(x, y)
        await self._page.mouse.wheel(dx, dy)

    async def _do_wait(self, action: AgentAction) -> None:
        duration = action.raw.get("duration", 1)
        await asyncio.sleep(min(duration, 5))

    async def _do_hold_key(self, action: AgentAction) -> None:
        if action.text:
            key = _normalize_key_combo(action.text)
            duration = action.raw.get("duration", 0.5)
            await self._page.keyboard.down(key)
            await asyncio.sleep(min(duration, 5))
            await self._page.keyboard.up(key)

    # -- Helpers ---------------------------------------------------------------

    def _screen_coords(self, action: AgentAction) -> tuple[int, int]:
        if action.coordinate is None:
            raise BrowserError(f"Action {action.action} requires coordinates")
        return self._screenshot.scale_coordinates_to_screen(*action.coordinate)


def _normalize_key_combo(combo: str) -> str:
    """Convert Anthropic key names to Playwright key names."""
    replacements = {
        "ctrl": "Control",
        "cmd": "Meta",
        "super": "Meta",
        "alt": "Alt",
        "shift": "Shift",
        "enter": "Enter",
        "return": "Enter",
        "tab": "Tab",
        "escape": "Escape",
        "esc": "Escape",
        "backspace": "Backspace",
        "delete": "Delete",
        "space": " ",
        "arrowup": "ArrowUp",
        "arrowdown": "ArrowDown",
        "arrowleft": "ArrowLeft",
        "arrowright": "ArrowRight",
    }
    parts = combo.split("+")
    normalized = [replacements.get(p.strip().lower(), p.strip()) for p in parts]
    return "+".join(normalized)


def _summarize(action: AgentAction) -> str:
    parts = []
    if action.coordinate:
        parts.append(f"at ({action.coordinate[0]}, {action.coordinate[1]})")
    if action.text:
        display = action.text[:40] + "..." if len(action.text) > 40 else action.text
        parts.append(f"text={display!r}")
    if action.scroll_direction:
        parts.append(f"{action.scroll_direction} {action.scroll_amount or 3}")
    return " ".join(parts) if parts else ""
