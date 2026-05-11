"""Shape of the intent payload encoded in OIG request justification."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any

INTENT_FENCE_START = "[INTENT_JSON]"
INTENT_FENCE_END = "[/INTENT_JSON]"
_INTENT_FENCE_RE = re.compile(
    re.escape(INTENT_FENCE_START) + r"\s*(\{.*?\})\s*" + re.escape(INTENT_FENCE_END),
    re.DOTALL,
)


@dataclass
class Intent:
    user_email: str
    agent: str            # e.g. "inventory"
    scope: str            # e.g. "inventory:write"
    product_name: str
    quantity_delta: int
    original_task: str
    submitted_at: str     # ISO8601
    fga_check_id: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))

    @classmethod
    def from_json(cls, raw: str) -> "Intent":
        data = json.loads(raw)
        return cls(**data)


def encode_justification(human_text: str, intent: Intent) -> str:
    """Return a justification string with human text plus a fenced JSON block."""
    return f"{human_text}\n\n{INTENT_FENCE_START}\n{intent.to_json()}\n{INTENT_FENCE_END}"


def decode_intent(justification: str) -> Intent | None:
    """Extract the Intent from a justification that was built with encode_justification."""
    match = _INTENT_FENCE_RE.search(justification or "")
    if not match:
        return None
    return Intent.from_json(match.group(1))


def find_comment(comments: list[dict[str, Any]], prefix: str) -> dict[str, Any] | None:
    """Return the first comment whose text starts with prefix, or None."""
    for c in comments or []:
        if (c.get("text") or "").startswith(prefix):
            return c
    return None
