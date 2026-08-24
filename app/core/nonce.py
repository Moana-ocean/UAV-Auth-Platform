"""Single-use nonce and short-lived session store."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass

from app.core.crypto import new_nonce


@dataclass
class SessionRecord:
    session_id: str
    uav_id: str
    nonce: bytes
    issued_at: float
    expires_at: float
    consumed: bool = False


class NonceStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, SessionRecord] = {}

    def create(self, uav_id: str, lifetime_s: float) -> SessionRecord:
        now = time.time()
        record = SessionRecord(
            session_id=uuid.uuid4().hex,
            uav_id=uav_id,
            nonce=new_nonce(),
            issued_at=now,
            expires_at=now + lifetime_s,
        )
        with self._lock:
            self._sessions[record.session_id] = record
        return record

    def consume(self, session_id: str, nonce: bytes, now: float | None = None) -> str:
        """Return OK, EXPIRED_CHALLENGE, REPLAY_DETECTED or MALFORMED_REQUEST.

        The nonce is marked consumed on every lookup that finds the session,
        including expired and mismatched-nonce cases.
        """
        now = time.time() if now is None else now
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return "MALFORMED_REQUEST"
            if record.consumed:
                return "REPLAY_DETECTED"
            record.consumed = True
            if now > record.expires_at:
                return "EXPIRED_CHALLENGE"
            if record.nonce != nonce:
                return "INVALID_SIGNATURE"
            return "OK"

    def peek(self, session_id: str) -> SessionRecord | None:
        with self._lock:
            return self._sessions.get(session_id)

    def reset(self) -> None:
        with self._lock:
            self._sessions.clear()
