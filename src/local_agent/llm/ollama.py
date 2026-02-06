import json
import re
import uuid

import httpx

from local_agent.config import settings
from local_agent.llm.base import AgentAction, AgentResponse, LLMProvider
from local_agent.utils.errors import LLMError
from local_agent.utils.logging import logger

OLLAMA_SYSTEM_PROMPT = """\
You control a browser by looking at screenshots. Respond with ONLY a JSON object.

Actions you can take:
- Click: {"action": "left_click", "coordinate": [300, 500]}
- Type: {"action": "type", "text": "Amsterdam"}
- Key press: {"action": "key", "text": "Enter"}
- Scroll down: {"action": "scroll", "coordinate": [640, 400], "scroll_direction": "down", "scroll_amount": 3}
- Done: {"action": "done", "text": "describe what you see on screen"}

The coordinate is [horizontal, vertical] in pixels. Look at the screenshot and estimate where to click.
After typing in a search box, always press Enter next.

IMPORTANT: When the task appears to be complete (the expected page or result is visible on screen), you MUST respond with the done action. Do NOT repeat actions that were already completed. If you already typed and pressed Enter, and the result page loaded, say done.

Output ONLY the JSON. No other text.
"""


class OllamaProvider(LLMProvider):
    """Ollama vision model provider for browser automation.

    Uses a simplified single-turn approach: each call sends only the system
    prompt, task instruction, action history summary, and the LATEST screenshot.
    Small vision models can't handle long multi-turn conversations well, so
    we condense history into a short text summary instead.
    """

    def __init__(self, scaled_width: int, scaled_height: int) -> None:
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._model = settings.ollama_model
        self._scaled_width = scaled_width
        self._scaled_height = scaled_height
        self._client = httpx.AsyncClient(timeout=180.0)
        self._action_history: list[str] = []
        self._empty_count: int = 0

    async def send(
        self,
        messages: list[dict],
        system: str | None = None,
    ) -> AgentResponse:
        # Extract the task instruction and latest screenshot from messages
        task_instruction = self._extract_task_instruction(messages)
        latest_image = self._extract_latest_image(messages)

        # Build a concise single-turn prompt
        user_prompt = self._build_user_prompt(task_instruction)

        ollama_messages = [
            {"role": "system", "content": OLLAMA_SYSTEM_PROMPT},
        ]

        user_msg: dict = {"role": "user", "content": user_prompt}
        if latest_image:
            user_msg["images"] = [latest_image]
        ollama_messages.append(user_msg)

        logger.info("Sending to Ollama: task=%s, history=%d actions, has_image=%s",
                     task_instruction[:60], len(self._action_history), bool(latest_image))

        try:
            resp = await self._client.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": ollama_messages,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 100},
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise LLMError(f"Ollama error: {exc}") from exc

        return self._parse_response(data)

    def _extract_task_instruction(self, messages: list[dict]) -> str:
        """Get the original task instruction from the first user message."""
        for msg in messages:
            if msg.get("role") != "user":
                continue
            content = msg.get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        return block["text"]
        return "Complete the task shown on screen."

    def _extract_latest_image(self, messages: list[dict]) -> str | None:
        """Get the most recent screenshot (base64) from messages."""
        latest = None
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "image":
                            latest = block["source"]["data"]
                        elif block.get("type") == "tool_result":
                            result_content = block.get("content", "")
                            if isinstance(result_content, list):
                                for item in result_content:
                                    if isinstance(item, dict) and item.get("type") == "image":
                                        latest = item["source"]["data"]
        return latest

    def _build_user_prompt(self, task: str) -> str:
        """Build a single-turn prompt with task + history summary."""
        parts = [f"TASK: {task}"]

        if self._action_history:
            history = "\n".join(f"  {i+1}. {a}" for i, a in enumerate(self._action_history[-6:]))
            parts.append(f"\nActions already completed:\n{history}")

            if len(self._action_history) >= 4:
                parts.append(
                    "\nLook at the screenshot. Has the task been completed? "
                    "If yes, respond with: {\"action\": \"done\", \"text\": \"description of result\"}\n"
                    "If not, what is the NEXT action?"
                )
            else:
                parts.append("\nWhat is the NEXT action? Look at the screenshot carefully.")
        else:
            parts.append("\nThis is the starting screenshot. What is the first action to take?")

        parts.append("\nRespond with ONLY a JSON object.")
        return "\n".join(parts)

    def _parse_response(self, data: dict) -> AgentResponse:
        content = data.get("message", {}).get("content", "")
        logger.info("Ollama response: %s", content[:500])

        action_data = self._extract_json(content)

        if not action_data or "action" not in action_data:
            self._empty_count += 1
            logger.warning("Ollama returned no valid action (%d consecutive)", self._empty_count)

            if self._empty_count >= 3:
                # After 3 consecutive failures, give up
                self._empty_count = 0
                return AgentResponse(
                    text=f"Model could not determine next action. Last response: {content[:200]}",
                    stop_reason="end_turn",
                    raw_content=[],
                )

            # Retry with a screenshot
            return AgentResponse(
                actions=[AgentAction(
                    tool_use_id=f"ollama_{uuid.uuid4().hex[:8]}",
                    action="screenshot",
                    raw={"action": "screenshot"},
                )],
                stop_reason="tool_use",
                raw_content=[],
            )

        # Valid action — reset empty counter
        self._empty_count = 0
        action_type = action_data.get("action", "")

        if action_type == "done":
            return AgentResponse(
                text=action_data.get("text", "Task completed"),
                stop_reason="end_turn",
                raw_content=[],
            )

        # Build an AgentAction
        tool_use_id = f"ollama_{uuid.uuid4().hex[:8]}"
        coordinate = None
        if "coordinate" in action_data:
            coord = action_data["coordinate"]
            if isinstance(coord, list) and len(coord) == 2:
                coordinate = tuple(coord)

        action = AgentAction(
            tool_use_id=tool_use_id,
            action=action_type,
            coordinate=coordinate,
            text=action_data.get("text"),
            scroll_direction=action_data.get("scroll_direction"),
            scroll_amount=action_data.get("scroll_amount"),
            raw=action_data,
        )

        # Record in history for context in next turn
        history_entry = action_type
        if coordinate:
            history_entry += f" at {list(coordinate)}"
        if action_data.get("text"):
            history_entry += f" '{action_data['text']}'"
        self._action_history.append(history_entry)

        return AgentResponse(
            actions=[action],
            stop_reason="tool_use",
            raw_content=[],
        )

    def _extract_json(self, text: str) -> dict | None:
        """Extract a JSON object from model output, handling markdown fences."""
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        match = re.search(r"\{[^{}]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        return None

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
