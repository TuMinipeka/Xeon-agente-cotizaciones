from __future__ import annotations

import json
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any

from xeon.application.ports.metrics import MetricEvent


def event_to_json(event: MetricEvent) -> dict[str, Any]:
    row = asdict(event)
    row["duration_ms"] = round(event.duration_ms, 3)
    row["estimated_cost"] = None if event.estimated_cost is None else str(event.estimated_cost)
    return row


class JsonlMetrics:
    """Appends one JSON object per event. Events hold no personal data by construction."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event: MetricEvent) -> None:
        line = json.dumps(event_to_json(event), ensure_ascii=False)
        with self._lock, self._path.open("a", encoding="utf-8") as journal:
            journal.write(line + "\n")
