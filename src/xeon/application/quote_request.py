from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

ClarificationReason = Literal["ambiguous_reference", "missing_units"]
QueryKind = Literal["exact_candidate", "ambiguous_reference", "missing_units"]

_MEASUREMENT_WITHOUT_CONTEXT = re.compile(
    r"(?i)(?:mide\s+)?\d+(?:[.,]\d+)?\s*[x\N{MULTIPLICATION SIGN}]\s*\d+"
    r"(?:[.,]\d+)?(?:\s*[x\N{MULTIPLICATION SIGN}]\s*\d+(?:[.,]\d+)?)?"
)
_UNIT_HINT = re.compile(r"(?i)\b(mm|cm|m|metros?|pulgadas?|kg|bultos?|unidades?)\b")
_SKU_LIKE = re.compile(r"(?i)^[a-z0-9]+(?:-[a-z0-9]+)+$")


@dataclass(frozen=True, slots=True)
class ClassifiedQuery:
    query: str
    reason: QueryKind


def classify_line_query(query: str) -> ClassifiedQuery:
    needle = query.strip()
    if _MEASUREMENT_WITHOUT_CONTEXT.search(needle) and _UNIT_HINT.search(needle) is None:
        return ClassifiedQuery(query=needle, reason="missing_units")
    if _SKU_LIKE.fullmatch(needle):
        return ClassifiedQuery(query=needle, reason="exact_candidate")
    return ClassifiedQuery(query=needle, reason="ambiguous_reference")
