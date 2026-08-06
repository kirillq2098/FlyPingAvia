"""Closed Beta Phase A: parse invite deep-link payloads."""

from __future__ import annotations

import re

_BETA_PAYLOAD = re.compile(r"^beta_([A-Za-z0-9_-]{1,32})$")


def parse_beta_invite_code(payload: str | None) -> str | None:
    """Извлечь cohort code из start payload ``beta_w1`` → ``w1``.

    Невалидное / не beta → None.
    """
    if not payload:
        return None
    text = str(payload).strip()
    m = _BETA_PAYLOAD.fullmatch(text)
    if not m:
        return None
    return m.group(1).lower()


def is_allowed_beta_code(code: str | None, *, allowed: set[str]) -> bool:
    if not code or not allowed:
        return False
    return code.lower() in allowed
