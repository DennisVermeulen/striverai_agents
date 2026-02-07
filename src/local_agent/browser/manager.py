from pathlib import Path

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from local_agent.config import settings
from local_agent.utils.errors import BrowserError
from local_agent.utils.logging import logger


class BrowserManager:
    """Manages the Playwright browser lifecycle."""

    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    @property
    def page(self) -> Page:
        if self._page is None:
            raise BrowserError("Browser not started — call start() first")
        return self._page

    @property
    def context(self) -> BrowserContext:
        if self._context is None:
            raise BrowserError("Browser not started — call start() first")
        return self._context

    async def start(self, storage_state_path: Path | None = None) -> Page:
        """Launch Chromium on the Xvfb display and return the active page."""
        logger.info("Starting browser...")

        self._playwright = await async_playwright().start()

        self._browser = await self._playwright.chromium.launch(
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-gpu",
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
            ],
        )

        # Restore session if a storage_state file exists
        context_kwargs: dict = {
            "viewport": {"width": settings.browser_width, "height": settings.browser_height},
            "ignore_https_errors": True,
        }
        if storage_state_path and storage_state_path.exists():
            logger.info("Restoring session from %s", storage_state_path)
            context_kwargs["storage_state"] = str(storage_state_path)

        self._context = await self._browser.new_context(**context_kwargs)
        self._page = await self._context.new_page()

        logger.info("Browser ready (%dx%d)", settings.browser_width, settings.browser_height)
        return self._page

    async def stop(self) -> None:
        """Shut down browser and Playwright."""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
        logger.info("Browser stopped")
