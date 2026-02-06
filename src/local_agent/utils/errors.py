class LocalAgentError(Exception):
    """Base exception for local_agent."""


class BrowserError(LocalAgentError):
    """Browser operation failed."""


class LLMError(LocalAgentError):
    """LLM provider error."""


class TaskError(LocalAgentError):
    """Task execution error."""


class SessionError(LocalAgentError):
    """Session save/load error."""
