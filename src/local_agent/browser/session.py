from pathlib import Path

from playwright.async_api import BrowserContext

from local_agent.config import settings
from local_agent.utils.errors import SessionError
from local_agent.utils.logging import logger

DEFAULT_SESSION_FILE = "default_session.json"


def session_path(name: str = DEFAULT_SESSION_FILE) -> Path:
    return settings.sessions_dir / name


async def save_session(context: BrowserContext, name: str = DEFAULT_SESSION_FILE) -> Path:
    """Persist cookies and localStorage to a JSON file."""
    path = session_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        await context.storage_state(path=str(path))
        logger.info("Session saved to %s", path)
        return path
    except Exception as exc:
        raise SessionError(f"Failed to save session: {exc}") from exc


def has_session(name: str = DEFAULT_SESSION_FILE) -> bool:
    return session_path(name).exists()


def get_session_path_if_exists(name: str = DEFAULT_SESSION_FILE) -> Path | None:
    p = session_path(name)
    return p if p.exists() else None
