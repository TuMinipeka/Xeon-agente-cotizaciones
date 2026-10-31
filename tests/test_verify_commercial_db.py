from __future__ import annotations

from unittest.mock import MagicMock

from scripts.verify_commercial_db import inspect_database


def test_inspection_stops_safely_when_schema_does_not_exist() -> None:
    connection = MagicMock()
    connection.execute.return_value.one.return_value = ("xeon", "17.6", False, False)
    assert inspect_database(connection) == {
        "database": "xeon",
        "server_version": "17.6",
        "vector_available": False,
        "commercial_schema": False,
    }
