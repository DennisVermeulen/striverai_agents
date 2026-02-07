from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from local_agent.browser.manager import BrowserManager
from local_agent.browser.screenshot import ScreenshotCapture
from local_agent.browser.session import get_session_path_if_exists
from local_agent.utils.logging import logger

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"


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
    app.state.batches = {}  # batch_id -> BatchState
    app.state.recorder = None  # BrowserRecorder | None

    logger.info("App started — browser ready")
    yield

    await browser_manager.stop()
    logger.info("App shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(title="Local Agent", version="0.1.0", lifespan=lifespan)

    # CORS for development (Vite dev server on different port)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from local_agent.api.routes import router
    from local_agent.api.websocket import router as ws_router

    app.include_router(router, prefix="/api")
    app.include_router(ws_router, prefix="/api")

    # Serve frontend static files if the build exists
    if FRONTEND_DIR.is_dir():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str):
            """Serve index.html for all non-API routes (SPA routing)."""
            file_path = FRONTEND_DIR / full_path
            if file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(FRONTEND_DIR / "index.html")

    return app
