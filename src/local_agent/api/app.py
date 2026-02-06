from contextlib import asynccontextmanager

from fastapi import FastAPI

from local_agent.browser.manager import BrowserManager
from local_agent.browser.screenshot import ScreenshotCapture
from local_agent.browser.session import get_session_path_if_exists
from local_agent.utils.logging import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start browser on startup, stop on shutdown."""
    browser_manager = BrowserManager()
    screenshot_capture = ScreenshotCapture()

    session_path = get_session_path_if_exists()
    await browser_manager.start(storage_state_path=session_path)

    app.state.browser = browser_manager
    app.state.screenshot = screenshot_capture
    app.state.tasks = {}  # task_id -> TaskState

    logger.info("App started — browser ready")
    yield

    await browser_manager.stop()
    logger.info("App shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(title="Local Agent", version="0.1.0", lifespan=lifespan)

    from local_agent.api.routes import router
    from local_agent.api.websocket import router as ws_router

    app.include_router(router)
    app.include_router(ws_router)

    return app
