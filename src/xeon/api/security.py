"""API access control: API key guard, rate limiting and trusted-proxy client addresses.

Standard library only. The API key lives in a file under secrets/ and is never logged.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from fastapi import HTTPException, Request

from xeon.config import Settings, SettingsError

LOCAL_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})
MIN_API_KEY_LENGTH = 24


@dataclass(frozen=True, slots=True)
class ApiAuth:
    """How `/v1/*` (except the signed webhook) is protected."""

    mode: Literal["key", "disabled", "unconfigured"]
    key_digest: bytes | None = None

    @classmethod
    def from_key(cls, key: str) -> ApiAuth:
        return cls("key", hashlib.sha256(key.encode("utf-8")).digest())

    def check(self, presented: str | None) -> bool:
        if self.mode != "key" or self.key_digest is None or not presented:
            return False
        digest = hashlib.sha256(presented.encode("utf-8")).digest()
        return hmac.compare_digest(digest, self.key_digest)


def build_api_auth(settings: Settings) -> ApiAuth:
    """Resolve API protection; production refuses to start without a key (fail closed)."""
    key = settings.read_api_key()
    if settings.app_env == "production":
        if settings.xeon_api_auth_disabled:
            raise SettingsError("XEON_API_AUTH_DISABLED no se admite con APP_ENV=production.")
        if key is None:
            raise SettingsError("APP_ENV=production requiere la clave de XEON_API_KEY_FILE.")
    if key is not None:
        return ApiAuth.from_key(key)
    return ApiAuth("disabled") if settings.xeon_api_auth_disabled else ApiAuth("unconfigured")


def bearer_token(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    scheme, _, value = header.partition(" ")
    return value.strip() if scheme.lower() == "bearer" and value.strip() else None


def api_key_guard(auth: ApiAuth) -> Callable[[Request], None]:
    """FastAPI dependency: 401 without a valid key, 503 when no key is configured."""

    def guard(request: Request) -> None:
        if auth.mode == "disabled":
            return
        if auth.mode == "unconfigured":
            raise HTTPException(
                status_code=503, detail="API sin clave configurada (XEON_API_KEY_FILE)."
            )
        if not auth.check(bearer_token(request)):
            raise HTTPException(
                status_code=401,
                detail="Clave de API invalida.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    return guard


def trusted_hosts(raw: str) -> frozenset[str]:
    hosts = set()
    for item in raw.split(","):
        text = item.strip()
        if text:
            hosts.add(str(ipaddress.ip_address(text)))
    return frozenset(hosts)


def client_ip(request: Request, trusted: frozenset[str]) -> str:
    """Peer address; behind a trusted proxy, the last untrusted X-Forwarded-For hop."""
    peer = request.client.host if request.client else "desconocido"
    if peer not in trusted:
        return peer
    forwarded = [
        h.strip() for h in request.headers.get("X-Forwarded-For", "").split(",") if h.strip()
    ]
    for hop in reversed(forwarded):
        if hop not in trusted:
            return hop
    return peer


def is_secure_request(request: Request, trusted: frozenset[str]) -> bool:
    """HTTPS directly, or forwarded as HTTPS by a trusted proxy."""
    if request.url.scheme == "https":
        return True
    peer = request.client.host if request.client else ""
    return peer in trusted and request.headers.get("X-Forwarded-Proto", "").lower() == "https"


def is_local_peer(request: Request) -> bool:
    return (request.client.host if request.client else "") in LOCAL_HOSTS


class SlidingWindowLimiter:
    """Allows `limit` hits per key in `window` seconds; remembers at most `max_keys` keys."""

    def __init__(
        self,
        *,
        limit: int,
        window_seconds: float = 60,
        max_keys: int = 10_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limit = limit
        self._window = window_seconds
        self._max_keys = max_keys
        self._clock = clock
        self._hits: OrderedDict[str, deque[float]] = OrderedDict()

    def allow(self, key: str) -> bool:
        now = self._clock()
        hits = self._hits.pop(key, None) or deque()
        while hits and hits[0] <= now - self._window:
            hits.popleft()
        allowed = len(hits) < self._limit
        if allowed:
            hits.append(now)
        self._hits[key] = hits
        while len(self._hits) > self._max_keys:
            self._hits.popitem(last=False)
        return allowed

    def retry_after(self, key: str) -> int:
        hits = self._hits.get(key)
        if not hits:
            return 1
        return max(1, int(hits[0] + self._window - self._clock()) + 1)
