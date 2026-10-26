"""Advisor panel authentication: PBKDF2 password hashes, sessions and login throttling.

Standard library only. Hashes live in a file under secrets/, never in code or logs.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

PBKDF2_ITERATIONS = 600_000
_SCHEME = "pbkdf2_sha256"


def hash_password(password: str, *, iterations: int = PBKDF2_ITERATIONS) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    encoded = (base64.b64encode(salt).decode(), base64.b64encode(digest).decode())
    return f"{_SCHEME}${iterations}${encoded[0]}${encoded[1]}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, rounds, salt_b64, digest_b64 = stored.split("$")
        if scheme != _SCHEME:
            return False
        salt = base64.b64decode(salt_b64, validate=True)
        expected = base64.b64decode(digest_b64, validate=True)
        iterations = int(rounds)
    except ValueError:
        return False
    if iterations < 1:
        return False
    actual = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations, len(expected)
    )
    return hmac.compare_digest(actual, expected)


# Verified against when the user does not exist, so timing does not reveal valid usernames.
# Same cost as a real hash: an unknown user must take as long as a known one (review M1).
_DUMMY_HASH = hash_password("sin-usuario")
MAX_PASSWORD_LENGTH = 128


def load_credentials(path: Path) -> dict[str, str]:
    """Read `usuario:hash` lines. The file must live inside a `secrets` directory."""
    if "secrets" not in path.parts:
        return {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    credentials: dict[str, str] = {}
    for line in lines:
        text = line.strip()
        if not text or text.startswith("#") or ":" not in text:
            continue
        user, stored = text.split(":", 1)
        credentials[user.strip().lower()] = stored.strip()
    return credentials


def authenticate(credentials: dict[str, str], username: str, password: str) -> str | None:
    user = username.strip().lower()
    stored = credentials.get(user)
    # Over-long passwords are refused after the same hashing work, never silently truncated.
    candidate = password if len(password) <= MAX_PASSWORD_LENGTH else ""
    valid = verify_password(candidate, stored if stored is not None else _DUMMY_HASH)
    return user if stored is not None and valid and candidate else None


class LoginThrottle:
    """Per-key failure counter with progressive lockout (30 s, 60 s, 120 s ... up to an hour)."""

    def __init__(
        self,
        *,
        max_attempts: int = 5,
        window_seconds: float = 900,
        base_lock_seconds: float = 30,
        max_lock_seconds: float = 3600,
        max_keys: int = 10_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max = max_attempts
        self._window = window_seconds
        self._base = base_lock_seconds
        self._cap = max_lock_seconds
        self._max_keys = max_keys
        self._clock = clock
        self._failures: dict[str, deque[float]] = {}
        self._locked_until: dict[str, float] = {}

    def _recent(self, key: str) -> deque[float]:
        failures = self._failures.setdefault(key, deque())
        cutoff = self._clock() - self._window
        while failures and failures[0] <= cutoff:
            failures.popleft()
        return failures

    def purge(self) -> None:
        """Drop keys with no recent failures and no active lock; bound memory."""
        now = self._clock()
        for key in list(self._failures):
            if self._locked_until.get(key, 0) <= now and not self._recent(key):
                self._failures.pop(key, None)
                self._locked_until.pop(key, None)
        while len(self._failures) > self._max_keys:
            oldest = next(iter(self._failures))
            self._failures.pop(oldest, None)
            self._locked_until.pop(oldest, None)

    def blocked(self, key: str) -> bool:
        return self._locked_until.get(key, 0) > self._clock()

    def retry_after(self, key: str) -> int:
        return max(1, int(self._locked_until.get(key, 0) - self._clock()) + 1)

    def failure(self, key: str) -> None:
        if len(self._failures) >= self._max_keys:
            self.purge()
        failures = self._recent(key)
        failures.append(self._clock())
        over = len(failures) - self._max
        if over >= 0:
            lock = min(self._base * (2**over), self._cap)
            self._locked_until[key] = self._clock() + lock

    def success(self, key: str) -> None:
        self._failures.pop(key, None)
        self._locked_until.pop(key, None)


@dataclass(frozen=True, slots=True)
class PanelSession:
    token: str
    username: str
    csrf: str
    expires_at: float


class SessionStore:
    def __init__(
        self,
        *,
        ttl_seconds: float = 8 * 3600,
        max_sessions: int = 200,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = ttl_seconds
        self._max_sessions = max_sessions
        self._clock = clock
        self._secret = secrets.token_bytes(32)
        # Only a keyed digest is retained; the cookie and CSRF tokens exist in requests.
        self._sessions: dict[str, tuple[str, float]] = {}

    def _key(self, token: str) -> str:
        return hmac.new(self._secret, token.encode(), "sha256").hexdigest()

    def _csrf(self, token: str) -> str:
        return hmac.new(self._secret, f"csrf:{token}".encode(), "sha256").hexdigest()

    @property
    def ttl_seconds(self) -> float:
        return self._ttl

    def purge(self) -> None:
        now = self._clock()
        for token in [t for t, (_, expires) in self._sessions.items() if expires <= now]:
            del self._sessions[token]
        while len(self._sessions) > self._max_sessions:
            del self._sessions[next(iter(self._sessions))]

    def create(self, username: str) -> PanelSession:
        self.purge()
        token = secrets.token_urlsafe(32)
        expires_at = self._clock() + self._ttl
        self._sessions[self._key(token)] = (username, expires_at)
        return PanelSession(
            token=token,
            username=username,
            csrf=self._csrf(token),
            expires_at=expires_at,
        )

    def get(self, token: str | None) -> PanelSession | None:
        if not token:
            return None
        key = self._key(token)
        record = self._sessions.get(key)
        if record is None:
            return None
        username, expires_at = record
        if expires_at <= self._clock():
            self._sessions.pop(key, None)
            return None
        return PanelSession(token, username, self._csrf(token), expires_at)

    def delete(self, token: str | None) -> None:
        if token:
            self._sessions.pop(self._key(token), None)
