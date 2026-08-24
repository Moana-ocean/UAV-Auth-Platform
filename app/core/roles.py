"""Role-based authorisation used by both mechanisms."""

from __future__ import annotations

from app.core.constants import ALLOWED_OPERATIONS


def authorise(role: int, requested_operation: str) -> bool:
    allowed = ALLOWED_OPERATIONS.get(int(role), frozenset())
    return requested_operation in allowed
