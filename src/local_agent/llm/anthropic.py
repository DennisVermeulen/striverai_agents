import anthropic

from local_agent.config import settings
from local_agent.llm.base import AgentAction, AgentResponse, LLMProvider
from local_agent.utils.errors import LLMError
from local_agent.utils.logging import logger


class AnthropicProvider(LLMProvider):
    """Claude Computer Use provider using the computer_20250124 tool."""

    BETA_FLAG = "computer-use-2025-01-24"
    TOOL_TYPE = "computer_20250124"

    def __init__(self, scaled_width: int, scaled_height: int) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._model = settings.llm_model
        self._max_tokens = settings.llm_max_tokens
        self._scaled_width = scaled_width
        self._scaled_height = scaled_height

    def _tool_definition(self) -> dict:
        return {
            "type": self.TOOL_TYPE,
            "name": "computer",
            "display_width_px": self._scaled_width,
            "display_height_px": self._scaled_height,
            "display_number": settings.display_num,
        }

    async def send(
        self,
        messages: list[dict],
        system: str | None = None,
    ) -> AgentResponse:
        kwargs: dict = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "tools": [self._tool_definition()],
            "messages": messages,
            "betas": [self.BETA_FLAG],
        }
        if system:
            kwargs["system"] = system

        try:
            response = await self._client.beta.messages.create(**kwargs)
        except anthropic.APIError as exc:
            raise LLMError(f"Anthropic API error: {exc}") from exc

        return self._parse_response(response)

    def _parse_response(self, response) -> AgentResponse:
        actions: list[AgentAction] = []
        text_parts: list[str] = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                action = self._parse_tool_use(block)
                actions.append(action)

        return AgentResponse(
            actions=actions,
            text="\n".join(text_parts) if text_parts else None,
            stop_reason=response.stop_reason,
            raw_content=response.content,
        )

    def _parse_tool_use(self, block) -> AgentAction:
        inp = block.input
        action_type = inp.get("action", "unknown")

        coordinate = None
        if "coordinate" in inp:
            coordinate = tuple(inp["coordinate"])

        return AgentAction(
            tool_use_id=block.id,
            action=action_type,
            coordinate=coordinate,
            text=inp.get("text"),
            scroll_direction=inp.get("scroll_direction"),
            scroll_amount=inp.get("scroll_amount"),
            raw=inp,
        )

    def build_screenshot_result(self, tool_use_id: str, screenshot_b64: str) -> dict:
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": screenshot_b64,
                    },
                }
            ],
        }

    def build_error_result(self, tool_use_id: str, error: str) -> dict:
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": error,
            "is_error": True,
        }
