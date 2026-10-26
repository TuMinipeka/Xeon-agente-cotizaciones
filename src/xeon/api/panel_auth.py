"""Advisor panel authentication: PBKDF2 password hashes, sessions and login throttling.

Standard library only. Hashes live in a file under secrets/, never in code or logs.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque
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
_DUMMY_HASH = hash_password("sin-usuario", iterations=1000)


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
    valid = verify_password(password, stored if stored is not None else _DUMMY_HASH)
    return user if stored is not None and valid else None


class LoginThrottle:
    """Blocks a key after repeated failures inside a sliding window."""

    def __init__(
        self,
        *,
        max_attempts: int = 5,
        window_seconds: float = 900,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max = max_attempts
        self._window = window_seconds
        self._clock = clock
        self._failures: dict[str, deque[float]] = defaultdict(deque)

    def _recent(self, key: str) -> deque[float]:
        failures = self._failures[key]
        cutoff = self._clock() - self._window
        while failures and failures[0] <= cutoff:
            failures.popleft()
        return failures

    def blocked(self, key: str) -> bool:
        return len(self._recent(key)) >= self._max

    def failure(self, key: str) -> None:
        self._recent(key).append(self._clock())

    def success(self, key: str) -> None:
        self._failures.pop(key, None)


@dataclass(frozen=True, slots=True)
class PanelSession:
    token: str
    username: str
    csrf: str
    expires_at: float


class SessionStore:
    def __init__(
        self, *, ttl_seconds: float = 8 * 3600, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._ttl = ttl_seconds
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

    def create(self, username: str) -> PanelSession:
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
