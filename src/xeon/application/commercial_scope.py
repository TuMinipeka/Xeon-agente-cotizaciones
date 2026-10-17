from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

ScopeKind = Literal["courtesy", "operational_help", "commercial", "mixed", "out_of_scope"]

_COURTESY_MESSAGES = frozenset(
    {
        "hola",
        "buenas",
        "buenos dias",
        "buenas tardes",
        "buenas noches",
        "gracias",
        "muchas gracias",
    }
)
_HELP_PHRASES = (
    "como funciona",
    "como usar",
    "como te uso",
    "que puedes hacer",
    "en que me ayudas",
    "ayuda para cotizar",
)
_SELECTION_PHRASES = (
    "la primera",
    "el primero",
    "opcion 1",
    "la segunda",
    "el segundo",
    "opcion 2",
    "la tercera",
    "el tercero",
    "opcion 3",
    "confirmo",
)
_COMMERCIAL_TERMS = frozenset(
    {
        "agro",
        "agroferreteria",
        "aire acondicionado",
        "alambre",
        "baldosa",
        "bloque",
        "bombillo",
        "bomba",
        "broca",
        "cable",
        "cemento",
        "cerradura",
        "clavo",
        "concreto",
        "construccion",
        "destornillador",
        "electricidad",
        "electrico",
        "ferreteria",
        "griferia",
        "herramienta",
        "ladrillo",
        "lamina",
        "llave",
        "manguera",
        "martillo",
        "material",
        "mezcla",
        "mortero",
        "pala",
        "pegante",
        "pintura",
        "pieza",
        "placa",
        "plomeria",
        "potrero",
        "pvc",
        "riego",
        "soldadura",
        "taladro",
        "teja",
        "tornillo",
        "tuberia",
        "tubo",
        "varilla",
    }
)
_OUT_OF_SCOPE_TERMS = frozenset(
    {
        "celular",
        "computador",
        "criptomoneda",
        "gpu",
        "laptop",
        "noticias",
        "pelicula",
        "politica",
        "programacion",
        "receta",
        "restaurante",
        "tarjeta grafica",
        "tarjetas graficas",
        "videojuego",
    }
)
_SEGMENT_SEPARATOR = re.compile(r"\s*(?:,|;|\by\b|\bademas\b|\btambien\b)\s*")
_WORD_RE = re.compile(r"[a-z0-9]+")
_SKU_LIKE_RE = re.compile(r"\b[a-z0-9]+(?:-[a-z0-9]+)+\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ScopeDecision:
    kind: ScopeKind
    commercial_query: str | None = None
    customer_message: str | None = None

    @property
    def blocks_llm(self) -> bool:
        return self.kind in {"courtesy", "operational_help", "out_of_scope"}


class CommercialScopePolicy:
    """Deterministic customer-facing scope gate executed before any LLM call."""

    def classify(self, message: str) -> ScopeDecision:
        cleaned = " ".join(message.split())
        normalized = _normalize(cleaned)
        if normalized in _COURTESY_MESSAGES:
            return ScopeDecision(
                kind="courtesy",
                customer_message=(
                    "¡Hola! Cuéntame qué material o herramienta necesitas y en qué cantidad."
                ),
            )

        if any(phrase in normalized for phrase in _HELP_PHRASES):
            return ScopeDecision(
                kind="operational_help",
                customer_message=(
                    "Dime qué producto necesitas, la cantidad y, si aplica, la sede donde quieres "
                    "consultarlo. Si encuentro varias opciones, te las mostraré por su nombre para "
                    "que elijas la correcta."
                ),
            )

        if any(phrase in normalized for phrase in _SELECTION_PHRASES):
            return ScopeDecision(kind="commercial", commercial_query=cleaned)

        if _SKU_LIKE_RE.search(cleaned) is not None:
            return ScopeDecision(kind="commercial", commercial_query=cleaned)

        segments = tuple(part for part in _SEGMENT_SEPARATOR.split(cleaned) if part)
        commercial_segments = tuple(part for part in segments if _is_commercial(part))
        rejected_segments = tuple(part for part in segments if _is_out_of_scope(part))

        if commercial_segments and rejected_segments:
            return ScopeDecision(
                kind="mixed",
                commercial_query=" y ".join(commercial_segments),
                customer_message=(
                    "Sobre la parte que no corresponde a la ferretería no manejo información. "
                    "Te ayudo con lo que sí tenemos dentro de nuestro catálogo."
                ),
            )
        if commercial_segments:
            return ScopeDecision(kind="commercial", commercial_query=cleaned)

        return ScopeDecision(
            kind="out_of_scope",
            customer_message=(
                "Somos una ferretería y no manejo información sobre ese tema. "
                "¿Necesitas ayuda con materiales, herramientas, plomería, electricidad o "
                "productos agroferreteros?"
            ),
        )


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(_WORD_RE.findall(without_accents))


def _contains_term(value: str, terms: frozenset[str]) -> bool:
    normalized = _normalize(value)
    padded = f" {normalized} "
    tokens = normalized.split()
    return any(
        f" {term} " in padded
        or (" " not in term and any(token == term or token.rstrip("s") == term for token in tokens))
        for term in terms
    )


def _is_commercial(value: str) -> bool:
    return _contains_term(value, _COMMERCIAL_TERMS)


def _is_out_of_scope(value: str) -> bool:
    return _contains_term(value, _OUT_OF_SCOPE_TERMS) or not _is_commercial(value)
