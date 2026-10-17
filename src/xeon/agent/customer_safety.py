from __future__ import annotations

import re
from collections.abc import Iterable

_URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>()]+", re.IGNORECASE)
_SKU_RE = re.compile(r"\b[A-Z]{2,}(?:-[A-Z0-9]+)+\b")
_INTERNAL_MARKERS = (
    "[hermes_",
    "confirmation_required",
    "create_quote_draft",
    "get_stock_by_branches",
    "semantic_candidates",
    "confirmed_selection",
    "llm_provider",
    "base de datos",
    "prompt interno",
    "status=draft",
)


class CustomerResponsePolicy:
    """Fail closed when a model exposes internals or an unregistered link."""

    def __init__(self, approved_links: Iterable[str] = ()) -> None:
        self._approved_links = frozenset(link.strip() for link in approved_links if link.strip())

    def sanitize(self, response: str, *, fallback: str) -> str:
        candidate = response.strip()
        if not candidate:
            return fallback

        lowered = candidate.casefold()
        if any(marker in lowered for marker in _INTERNAL_MARKERS):
            return fallback
        if "sku" in lowered or _SKU_RE.search(candidate) is not None:
            return fallback

        links = tuple(match.group(0).rstrip(".,;:!?") for match in _URL_RE.finditer(candidate))
        if any(link not in self._approved_links for link in links):
            return fallback
        return candidate
