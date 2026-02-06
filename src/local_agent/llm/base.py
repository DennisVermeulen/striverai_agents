from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentAction:
    """A single action returned by the LLM."""

    tool_use_id: str
    action: str  # screenshot, left_click, type, key, scroll, etc.
    coordinate: tuple[int, int] | None = None
    text: str | None = None
    scroll_direction: str | None = None  # up, down, left, right
    scroll_amount: int | None = None
    raw: dict = field(default_factory=dict)


@dataclass
class AgentResponse:
    """Full response from the LLM, which may contain text and/or actions."""

    actions: list[AgentAction] = field(default_factory=list)
    text: str | None = None
    stop_reason: str | None = None
    raw_content: list[Any] = field(default_factory=list)

    @property
    def has_actions(self) -> bool:
        return len(self.actions) > 0

    @property
    def is_done(self) -> bool:
        return self.stop_reason == "end_turn" and not self.has_actions


class LLMProvider(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    async def send(
        self,
        messages: list[dict],
        system: str | None = None,
    ) -> AgentResponse:
        """Send messages to the LLM and get back actions/text."""
        ...

    @abstractmethod
    def build_screenshot_result(
        self,
        tool_use_id: str,
        screenshot_b64: str,
    ) -> dict:
        """Build a tool_result message containing a screenshot image."""
        ...

    @abstractmethod
    def build_error_result(
        self,
        tool_use_id: str,
        error: str,
    ) -> dict:
        """Build a tool_result message with is_error: true."""
        ...
