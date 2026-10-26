from xeon.application.ports.funnel import FunnelState


class InMemoryFunnelRepository:
    def __init__(self) -> None:
        self._states: dict[str, FunnelState] = {}

    def get(self, conversation_key: str) -> FunnelState:
        return self._states.get(conversation_key, FunnelState())

    def save(self, conversation_key: str, state: FunnelState) -> None:
        self._states[conversation_key] = state
