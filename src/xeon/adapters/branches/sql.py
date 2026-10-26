from __future__ import annotations

from xeon.adapters.sql.connection import SqlReader, mapped
from xeon.connectors.schema import ConnectorConfig
from xeon.domain.branch import Branch


class SqlBranchDirectory:
    def __init__(self, reader: SqlReader, config: ConnectorConfig) -> None:
        self._reader = reader
        self._config = config

    def list_branches(self) -> tuple[Branch, ...]:
        query = self._config.list_branches
        branches = []
        for row in self._reader.rows(query):
            aliases_raw = mapped(row, query, "aliases", "")
            aliases = tuple(
                alias.strip() for alias in str(aliases_raw or "").split("|") if alias.strip()
            )
            branches.append(
                Branch(
                    id=str(mapped(row, query, "id")),
                    name=str(mapped(row, query, "name")),
                    aliases=aliases,
                )
            )
        return tuple(branches)
