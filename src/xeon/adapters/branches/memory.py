from xeon.domain.branch import Branch

SYNTHETIC_BRANCHES = (
    Branch("sede-centro", "Ferreteria Demo XEON Centro", ("centro",)),
    Branch("sede-norte", "Ferreteria Demo XEON Norte", ("norte",)),
    Branch("sede-sur", "Ferreteria Demo XEON Sur", ("sur",)),
)


class InMemoryBranchDirectory:
    def __init__(self, branches: tuple[Branch, ...] = SYNTHETIC_BRANCHES) -> None:
        self._branches = branches

    def list_branches(self) -> tuple[Branch, ...]:
        return self._branches
