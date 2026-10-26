import re
import unicodedata
from typing import Protocol

from xeon.domain.branch import Branch


class BranchDirectory(Protocol):
    def list_branches(self) -> tuple[Branch, ...]: ...


def resolve_branch(text: str, directory: BranchDirectory | None) -> Branch | None:
    if directory is None:
        return None
    normalized = unicodedata.normalize("NFKD", text.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    matches: list[Branch] = []
    for branch in directory.list_branches():
        terms = (branch.id, branch.name, *branch.aliases)
        if any(
            re.search(rf"(?<!\w){re.escape(term.casefold())}(?!\w)", normalized) for term in terms
        ):
            matches.append(branch)
    return matches[0] if len(matches) == 1 else None
