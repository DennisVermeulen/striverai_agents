from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

from local_agent.config import settings
from local_agent.utils.logging import logger


@dataclass
class ElementInfo:
    tag: str = ""
    text: str = ""
    aria_label: str = ""
    placeholder: str = ""
    role: str = ""
    name: str = ""
    input_type: str = ""
    tooltip: str = ""
    title: str = ""
    contenteditable: bool = False
    parent_context: str = ""
    label: str = ""

    def to_dict(self) -> dict:
        d = {k: v for k, v in {
            "tag": self.tag,
            "text": self.text,
            "aria_label": self.aria_label,
            "placeholder": self.placeholder,
            "role": self.role,
            "name": self.name,
            "input_type": self.input_type,
            "tooltip": self.tooltip,
            "title": self.title,
            "parent_context": self.parent_context,
            "label": self.label,
        }.items() if v}
        if self.contenteditable:
            d["contenteditable"] = True
        return d

    @classmethod
    def from_dict(cls, data: dict) -> ElementInfo:
        return cls(
            tag=data.get("tag", ""),
            text=data.get("text", ""),
            aria_label=data.get("aria_label", ""),
            placeholder=data.get("placeholder", ""),
            role=data.get("role", ""),
            name=data.get("name", ""),
            input_type=data.get("input_type", ""),
            tooltip=data.get("tooltip", ""),
            title=data.get("title", ""),
            contenteditable=data.get("contenteditable", False),
            parent_context=data.get("parent_context", ""),
            label=data.get("label", ""),
        )


@dataclass
class WorkflowStep:
    action: str  # click, type, key, navigate
    description: str = ""
    coordinates: list[int] | None = None
    text: str = ""
    key: str = ""
    url: str = ""
    element: ElementInfo = field(default_factory=ElementInfo)

    def to_dict(self) -> dict:
        d: dict = {"action": self.action}
        if self.description:
            d["description"] = self.description
        if self.coordinates:
            d["coordinates"] = self.coordinates
        if self.text:
            d["text"] = self.text
        if self.key:
            d["key"] = self.key
        if self.url:
            d["url"] = self.url
        elem = self.element.to_dict()
        if elem:
            d["element"] = elem
        return d

    @classmethod
    def from_dict(cls, data: dict) -> WorkflowStep:
        elem = ElementInfo.from_dict(data.get("element", {}))
        return cls(
            action=data["action"],
            description=data.get("description", ""),
            coordinates=data.get("coordinates"),
            text=data.get("text", ""),
            key=data.get("key", ""),
            url=data.get("url", ""),
            element=elem,
        )


@dataclass
class Workflow:
    name: str
    description: str = ""
    start_url: str = ""
    steps: list[WorkflowStep] = field(default_factory=list)
    recorded_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_yaml(self) -> str:
        data = {
            "name": self.name,
            "description": self.description,
            "recorded_at": self.recorded_at,
            "start_url": self.start_url,
            "steps": [s.to_dict() for s in self.steps],
        }
        return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)

    @classmethod
    def from_yaml(cls, content: str) -> Workflow:
        data = yaml.safe_load(content)
        steps = [WorkflowStep.from_dict(s) for s in data.get("steps", [])]
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            start_url=data.get("start_url", ""),
            steps=steps,
            recorded_at=data.get("recorded_at", ""),
        )

    def to_instruction(self) -> str:
        """Convert workflow steps to a natural-language instruction for the AI agent."""
        lines = []
        if self.description:
            lines.append(f"Task: {self.description}")
        else:
            lines.append(f"Task: Replay recorded workflow '{self.name}'")

        if self.start_url:
            lines.append(f"Starting page: {self.start_url}")
        lines.append("")
        lines.append(
            "Follow these steps in order. Use the screenshot to find each element. "
            "The hints about screen position and element context should help you locate them."
        )
        lines.append("")

        for i, step in enumerate(self.steps, 1):
            lines.append(self._step_to_instruction(i, step))

        lines.append("")
        lines.append(
            "After completing ALL steps above, report that the task is done. "
            "Do not add extra steps that were not listed."
        )
        return "\n".join(lines)

    @staticmethod
    def _step_to_instruction(num: int, step: WorkflowStep) -> str:
        """Generate a detailed instruction line for a single step."""
        el = step.element
        parts = []

        if step.action == "click":
            # Build target description with multiple identifiers
            target = _describe_element_detailed(el)
            parts.append(f"{num}. CLICK: {target}")
            if step.coordinates:
                parts.append(f"   (approximate position: x={step.coordinates[0]}, y={step.coordinates[1]})")

        elif step.action == "type":
            target = _describe_field(el)
            parts.append(f"{num}. TYPE: '{step.text}' into {target}")
            if el.contenteditable:
                parts.append("   (this is a rich text field, not a regular input)")

        elif step.action == "key":
            parts.append(f"{num}. PRESS: {step.key} key")

        elif step.action == "navigate":
            parts.append(f"{num}. NAVIGATE: Go to {step.url}")

        return "\n".join(parts)

    def save(self, directory: Path | None = None) -> Path:
        """Save workflow as YAML file."""
        d = directory or settings.workflows_dir
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{self.name}.yaml"
        path.write_text(self.to_yaml(), encoding="utf-8")
        logger.info("Workflow saved to %s", path)
        return path

    @classmethod
    def load(cls, name: str, directory: Path | None = None) -> Workflow:
        d = directory or settings.workflows_dir
        path = d / f"{name}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Workflow '{name}' not found")
        return cls.from_yaml(path.read_text(encoding="utf-8"))

    @classmethod
    def list_all(cls, directory: Path | None = None) -> list[Workflow]:
        d = directory or settings.workflows_dir
        if not d.exists():
            return []
        workflows = []
        for path in sorted(d.glob("*.yaml")):
            try:
                workflows.append(cls.from_yaml(path.read_text(encoding="utf-8")))
            except Exception as e:
                logger.warning("Failed to load workflow %s: %s", path.name, e)
        return workflows

    @classmethod
    def delete(cls, name: str, directory: Path | None = None) -> bool:
        d = directory or settings.workflows_dir
        path = d / f"{name}.yaml"
        if path.exists():
            path.unlink()
            logger.info("Workflow '%s' deleted", name)
            return True
        return False


def _describe_element(element: ElementInfo) -> str:
    """Generate a human-readable description of an element (short version for YAML)."""
    if element.aria_label:
        return f"'{element.aria_label}'"
    if element.tooltip:
        return f"'{element.tooltip}'"
    if element.title:
        return f"'{element.title}'"
    if element.text:
        text = element.text[:40] + ("..." if len(element.text) > 40 else "")
        return f"'{text}'"
    if element.placeholder:
        return f"'{element.placeholder}' field"
    if element.role:
        return f"{element.role}"
    return f"{element.tag or 'element'}"


def _describe_element_detailed(element: ElementInfo) -> str:
    """Generate a detailed description for AI instruction — multiple identifiers."""
    identifiers = []

    # Primary identifier
    if element.aria_label:
        identifiers.append(f"the element labeled '{element.aria_label}'")
    elif element.tooltip:
        identifiers.append(f"the element with tooltip '{element.tooltip}'")
    elif element.title:
        identifiers.append(f"the element titled '{element.title}'")
    elif element.text:
        text = element.text[:50]
        identifiers.append(f"the element with text '{text}'")
    elif element.role:
        identifiers.append(f"the {element.role} element")
    else:
        identifiers.append(f"the {element.tag or 'element'}")

    # Additional context
    if element.role and element.role not in str(identifiers):
        identifiers.append(f"role: {element.role}")
    if element.parent_context:
        identifiers.append(f"inside the '{element.parent_context}' area")

    return ", ".join(identifiers)


def _describe_field(element: ElementInfo) -> str:
    """Generate a detailed description of an input field for AI instruction."""
    if element.aria_label:
        return f"the '{element.aria_label}' field"
    if element.label:
        return f"the '{element.label}' field"
    if element.placeholder:
        return f"the field with placeholder '{element.placeholder}'"
    if element.name:
        return f"the '{element.name}' field"
    if element.parent_context:
        return f"the input field inside '{element.parent_context}'"
    return "the text field"


def process_raw_events(events: list[dict], start_url: str = "") -> list[WorkflowStep]:
    """Convert raw JS events into clean workflow steps.

    Applies these optimizations:
    - Click followed by type on same element → skip the click (it's just focusing)
    - Consecutive type events on same element → keep only the last value
    - Skip Backspace/Delete (typo corrections) when followed by more typing
    - Skip Gmail-style hash navigations with unique compose IDs
    - Deduplicate: if we already typed in a field, skip duplicate types with same/less text
    - Generate human-readable descriptions
    """
    if not events:
        return []

    # Phase 1: collect raw steps
    raw_steps: list[WorkflowStep] = []

    i = 0
    while i < len(events):
        event = events[i]
        etype = event.get("type", "")

        if etype == "navigate":
            url = event.get("url", "")
            # Skip hash-only navigations with unique IDs (Gmail compose etc)
            if url and url != start_url and not _is_ephemeral_navigation(url, start_url):
                raw_steps.append(WorkflowStep(
                    action="navigate",
                    url=url,
                    description=f"Navigate to {url}",
                ))

        elif etype == "click":
            # Check if next non-key event is a type on the same element → skip click
            next_relevant = _next_non_backspace(events, i + 1)
            if next_relevant and next_relevant.get("type") == "type":
                if _elements_match(event.get("element", {}), next_relevant.get("element", {})):
                    i += 1
                    continue

            elem = ElementInfo.from_dict(event.get("element", {}))
            coords = [event.get("x", 0), event.get("y", 0)]
            target = _describe_element(elem)
            raw_steps.append(WorkflowStep(
                action="click",
                coordinates=coords,
                element=elem,
                description=f"Click {target}",
            ))

        elif etype == "type":
            elem_data = event.get("element", {})
            text = event.get("text", "")

            # Look ahead: merge consecutive types on same element, skip interleaved backspaces
            j = i + 1
            while j < len(events):
                ntype = events[j].get("type", "")
                if ntype == "type" and _elements_match(elem_data, events[j].get("element", {})):
                    text = events[j].get("text", "")
                    elem_data = events[j].get("element", {})
                    j += 1
                elif ntype == "key" and events[j].get("key") in ("Backspace", "Delete"):
                    # Skip backspace between types — it's a typo correction
                    j += 1
                else:
                    break
            i = j - 1  # will be incremented at end of loop

            if text:
                elem = ElementInfo.from_dict(elem_data)
                target = _describe_element(elem)
                raw_steps.append(WorkflowStep(
                    action="type",
                    text=text,
                    element=elem,
                    description=f"Type '{text}' in {target}",
                ))

        elif etype == "key":
            key = event.get("key", "")
            # Skip standalone backspace/delete — likely typo corrections
            if key in ("Backspace", "Delete"):
                i += 1
                continue
            if key:
                elem = ElementInfo.from_dict(event.get("element", {}))
                raw_steps.append(WorkflowStep(
                    action="key",
                    key=key,
                    element=elem,
                    description=f"Press {key}",
                ))

        i += 1

    # Phase 2: deduplicate — remove repeated types on same field, keep last value
    return _deduplicate_steps(raw_steps)


def _is_ephemeral_navigation(url: str, start_url: str) -> bool:
    """Detect navigations that are just URL hash changes with unique IDs (e.g. Gmail compose)."""
    # Strip everything after # and compare base URLs
    base_new = url.split("#")[0]
    base_start = start_url.split("#")[0] if start_url else ""
    if base_new != base_start:
        return False
    # If the hash part contains a long random-looking string (>20 chars), it's ephemeral
    fragment = url.split("#", 1)[1] if "#" in url else ""
    # Gmail compose IDs look like: inbox?compose=DmwnWslzCnrMjZ...
    if "compose=" in fragment:
        compose_id = fragment.split("compose=", 1)[1]
        if len(compose_id) > 20:
            return True
    return False


def _next_non_backspace(events: list[dict], start: int) -> dict | None:
    """Find next event that isn't a Backspace/Delete key press."""
    for j in range(start, min(start + 5, len(events))):
        if events[j].get("type") == "key" and events[j].get("key") in ("Backspace", "Delete"):
            continue
        return events[j]
    return None


def _deduplicate_steps(steps: list[WorkflowStep]) -> list[WorkflowStep]:
    """Remove redundant steps: duplicate types on same field, clicks on field we already typed in."""
    result: list[WorkflowStep] = []
    # Track which fields have been typed into (by aria_label)
    typed_fields: dict[str, str] = {}  # field_id -> latest text

    for step in steps:
        if step.action == "type":
            field_id = step.element.aria_label or step.element.name or step.element.placeholder or ""
            if field_id:
                if field_id in typed_fields and typed_fields[field_id] == step.text:
                    # Exact duplicate type — skip
                    continue
                typed_fields[field_id] = step.text
                # Remove any previous type step for this field from result
                result = [s for s in result if not (
                    s.action == "type"
                    and (s.element.aria_label or s.element.name or s.element.placeholder or "") == field_id
                )]
            result.append(step)

        elif step.action == "click":
            # Skip click on a field we're about to type in (or already typed in)
            click_field = step.element.aria_label or step.element.name or step.element.placeholder or ""
            if click_field and click_field in typed_fields:
                continue
            result.append(step)

        else:
            result.append(step)

    return result


def _elements_match(a: dict, b: dict) -> bool:
    """Check if two element info dicts refer to the same element."""
    for key in ("aria_label", "name", "placeholder", "label", "tooltip"):
        va = a.get(key, "")
        vb = b.get(key, "")
        if va and vb and va == vb:
            return True
    return False
