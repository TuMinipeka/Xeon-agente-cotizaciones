"""Shared validation of required domain text fields."""


def require_text(value: str, *, field: str, error: type[Exception]) -> str:
    text = value.strip()
    if not text:
        raise error(f"{field} es obligatorio.")
    return text
