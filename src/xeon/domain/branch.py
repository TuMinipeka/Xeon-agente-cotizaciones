from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Branch:
    id: str
    name: str
    aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.name.strip():
            raise ValueError("La sede requiere id y nombre visible.")
