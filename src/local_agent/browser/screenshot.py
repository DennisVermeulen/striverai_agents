import base64
import math
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image
from playwright.async_api import Page

from local_agent.config import settings
from local_agent.utils.logging import logger


def _scale_factor(width: int, height: int, max_dim: int = 1568) -> float:
    """Calculate scale factor to meet Anthropic's image constraints.

    API limits: max 1568px longest edge, ~1.15 megapixels total.
    We pre-scale so Claude's returned coordinates match our scaled image,
    and we scale them back up when executing actions.
    """
    long_edge = max(width, height)
    total_pixels = width * height

    long_edge_scale = max_dim / long_edge
    total_pixels_scale = math.sqrt(1_150_000 / total_pixels)

    return min(1.0, long_edge_scale, total_pixels_scale)


class ScreenshotCapture:
    """Captures and scales browser screenshots for the LLM."""

    def __init__(self) -> None:
        self.scale: float = 1.0
        self.scaled_width: int = settings.browser_width
        self.scaled_height: int = settings.browser_height
        self._compute_scale()

    def _compute_scale(self) -> None:
        self.scale = _scale_factor(
            settings.browser_width,
            settings.browser_height,
            settings.screenshot_max_dimension,
        )
        self.scaled_width = int(settings.browser_width * self.scale)
        self.scaled_height = int(settings.browser_height * self.scale)
        logger.info(
            "Screenshot scale: %.3f (%dx%d → %dx%d)",
            self.scale,
            settings.browser_width,
            settings.browser_height,
            self.scaled_width,
            self.scaled_height,
        )

    def scale_coordinates_to_screen(self, x: int, y: int) -> tuple[int, int]:
        """Convert coordinates from scaled screenshot space to actual screen space."""
        return int(x / self.scale), int(y / self.scale)

    async def capture(self, page: Page, *, save: bool = False) -> str:
        """Take a screenshot, resize it, and return base64-encoded PNG."""
        raw_bytes = await page.screenshot(type="png")

        # Resize using Pillow
        import io

        img = Image.open(io.BytesIO(raw_bytes))
        if self.scale < 1.0:
            img = img.resize((self.scaled_width, self.scaled_height), Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        if save:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            path = settings.screenshots_dir / f"screenshot_{ts}.png"
            path.write_bytes(png_bytes)
            logger.debug("Screenshot saved to %s", path)

        return base64.b64encode(png_bytes).decode("utf-8")

    async def capture_bytes(self, page: Page) -> bytes:
        """Take a screenshot and return raw PNG bytes (for API responses)."""
        raw_bytes = await page.screenshot(type="png")
        import io

        img = Image.open(io.BytesIO(raw_bytes))
        if self.scale < 1.0:
            img = img.resize((self.scaled_width, self.scaled_height), Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
