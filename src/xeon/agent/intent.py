"""Validated model intent output with a local, deterministic fallback."""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from xeon.agent.toolbelt import _extract_requested_quantity
from xeon.application.ports.branches import BranchDirectory, resolve_branch
from xeon.application.ports.conversation_memory import PendingCandidates


class IntentKind(StrEnum):
    CONSULTAR_PRODUCTO = "consultar_producto"
    AGREGAR = "agregar"
    MODIFICAR_CANTIDAD = "modificar_cantidad"
    QUITAR = "quitar"
    ELEGIR_OPCION = "elegir_opcion"
    RESPONDER_PENDIENTE = "responder_pendiente"
    VER_RESUMEN_TOTAL = "ver_resumen_total"
    CONSULTAR_STOCK = "consultar_stock"
    CONSULTAR_POLITICA = "consultar_politica"
    ASESORIA_PROYECTO = "asesoria_proyecto"
    HIPOTETICA = "hipotetica"
    SALUDO = "saludo"
    FUERA_DE_ALCANCE = "fuera_de_alcance"


class ProjectEntities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    length_m: Decimal | None = None
    width_m: Decimal | None = None
    purpose: str | None = None
    whole_surface: bool | None = None


class Intent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: IntentKind
    product: str | None = None
    quantity: Decimal | None = Field(default=None, gt=0)
    branch: str | None = None
    attributes: dict[str, str] = Field(default_factory=dict)
    policy: str | None = None
    project: ProjectEntities | None = None
    source_text: str = ""


class IntentBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intents: tuple[Intent, ...] = Field(min_length=1)


_WORD_NUMBERS = {"una": Decimal(1), "uno": Decimal(1), "dos": Decimal(2), "tres": Decimal(3)}
_DIMENSIONS = re.compile(
    r"\b(\d+(?:[.,]\d+)?)\s*[x\u00d7]\s*(\d+(?:[.,]\d+)?)\s*(?:m|metros?)?\b", re.I
)
_OUTSIDE = re.compile(
    r"\b(?:tarjetas? graficas?|criptomonedas?|chistes?|poemas?|"
    r"peliculas?|videojuegos?|noticias?|restaurantes?)\b",
    re.I,
)
_POLICY = re.compile(
    r"\b(?:pagar|pago|tarjeta|efectivo|recoger|recojo|recogida|retiro|"
    r"domicilio|envio|entrega|horario|facturaci[oó]n)\b",
    re.I,
)
_PROJECT = re.compile(
    r"\b(?:corral|ganado|proyecto|superficie|piso de concreto|pavimentar)\b", re.I
)
_STOCK = re.compile(r"\b(?:disponib|existencias?|inventario|hay\s+stock|agotad)\w*", re.I)
_SUMMARY = re.compile(
    r"\b(?:resum|total|cu[aá]nto llevo|producto por producto|mi cotizaci[oó]n|"
    r"precio de lista)\w*",
    re.I,
)
_HYPOTHETICAL = re.compile(
    r"\b(?:qu[eé]\s+(?:descuento|precio)|si\s+(?:llevo|pido)|hipot[eé]tic)\w*", re.I
)
_REMOVE = re.compile(r"\b(?:quita|quitar|elimina|saca|retira)\w*|\bno\s+(?:quiero|va)\b", re.I)
_MODIFY = re.compile(
    r"\b(?:cambia|cambie|c[aá]mbialo|modifica|ajusta|reduce|sube)\w*|"
    r"\b(?:mejor\s+)?(?:d[eé]jala|d[eé]jalo|d[eé]jamelo|ponle|pon|deja)\s+(?:solo\s+|en\s+)?\d+|"
    r"\bno\s+es\s+\d+\s+son\s+\d+\b|\bsolo\s+\d+\b|"
    r"\bnom[aá]s\s+(?:en\s+)?\d+\b",
    re.I,
)
_ADD = re.compile(r"\b(?:agrega|a[nñ]ade|suma|deja|quiero|necesito|dame|cotiza)\w*", re.I)


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in value if not unicodedata.combining(char))


def _quantity(text: str) -> Decimal | None:
    correction = re.search(
        r"\bno\s+es\s+\d+(?:[.,]\d+)?\s+son\s+(\d+(?:[.,]\d+)?)", _normalize(text)
    )
    if correction is not None:
        return Decimal(correction.group(1).replace(",", "."))
    if re.search(r"\b\d+\s*/\s*\d+\b", text) and not re.search(
        r"\b\d+\s+(?:tubos?|unidades?|bultos?)\b", text, re.I
    ):
        return None
    parsed = _extract_requested_quantity(text)
    if parsed is not None:
        return parsed
    normalized = _normalize(text)
    multiplier = re.search(r"\bx\s*(\d+(?:[.,]\d+)?)\b", normalized)
    if multiplier is not None:
        return Decimal(multiplier.group(1).replace(",", "."))
    match = re.search(r"\b(\d+(?:[.,]\d+)?)\b", normalized)
    if match is not None and _DIMENSIONS.search(normalized) is None:
        raw = match.group(1).replace(",", ".")
        try:
            value = Decimal(raw)
            return value if value > 0 else None
        except Exception:
            return None
    for word, value in _WORD_NUMBERS.items():
        if re.search(rf"\b{word}\b", normalized):
            return value
    return None


def is_absolute_quantity(text: str) -> bool:
    normalized = _normalize(text)
    return bool(
        _MODIFY.search(normalized)
        or re.search(r"\b(?:en|a)\s+\d+\s+(?:bultos?|palas?)\b", normalized)
    )


def is_explicit_addition(text: str) -> bool:
    return re.search(r"\b(?:agrega|agregame|suma|otros?|m[aá]s)\b", _normalize(text)) is not None


def _product_phrase(text: str) -> str | None:
    cleaned = re.sub(
        r"(?i)^\s*(?:y\s+)?(?:agregame|agrega|anade|deja|quiero|necesito|dame|cotizame|cotiza)\s+",
        "",
        text,
    )
    cleaned = re.sub(
        r"(?i)^\s*(?:\d+|una?|dos|tres)\s+(?:bultos?|unidades?)\s*(?:de\s+)?", "", cleaned
    )
    cleaned = re.sub(r"(?i)\s*[x\u00d7]\s*\d+\s*$", "", cleaned)
    cleaned = re.sub(r"(?i)^\s*(?:dos|una?|tres|\d+)\s+", "", cleaned)
    cleaned = cleaned.strip(" ¿?.,!")
    return cleaned or None


def _from_clause(
    kind: IntentKind,
    clause: str,
    *,
    product: str | None = None,
    branches: BranchDirectory | None = None,
) -> Intent:
    return Intent(
        kind=kind,
        product=product,
        quantity=_quantity(clause),
        branch=resolved.id if (resolved := resolve_branch(clause, branches)) else None,
        source_text=clause,
    )


def fallback_intents(
    message: str,
    *,
    pending: PendingCandidates | None = None,
    branches: BranchDirectory | None = None,
) -> IntentBatch:
    cleaned = " ".join(message.split())
    normalized = _normalize(cleaned)
    if normalized in {"hola", "buenas", "buenos dias", "gracias"}:
        return IntentBatch(intents=(Intent(kind=IntentKind.SALUDO, source_text=cleaned),))
    if pending is not None and (
        re.search(r"\b(?:el|del|opcion)\s*[1-3]\b", normalized)
        or re.fullmatch(r"\s*[1-3]\s*", cleaned)
        or any(
            term in normalized
            for term in (
                "redonda",
                "cuadrada",
                "fibra",
                "madera",
                "opcion",
                "primero",
                "primera",
                "segundo",
                "segunda",
                "tercero",
                "tercera",
            )
        )
        or any(_normalize(name) in normalized for name in pending.names)
    ):
        return IntentBatch(
            intents=(Intent(kind=IntentKind.ELEGIR_OPCION, product=cleaned, source_text=cleaned),)
        )

    cleaned = re.sub(r",\s+(?=\d+\s+(?:bultos?|tubos?|metros?|unidades?))", " ; ", cleaned)
    clauses = re.split(
        r"\s+y\s+(?=(?:deja|agrega|anade|quita|busca|\d+|si\s+|"
        r"que\s+|cuantos?|cu[aá]l|el\s+domicilio|domicilio|envio|entrega|los\s+|"
        r"llevo\s+|tambien\s+))",
        cleaned.replace(";", " ; "),
        flags=re.I,
    )
    clauses = [part for clause in clauses for part in clause.split(" ; ")]
    intents: list[Intent] = []
    for clause in clauses:
        clause = clause.strip(" ¿?.,!")
        if not clause:
            continue
        if _OUTSIDE.search(_normalize(clause)):
            intents.append(Intent(kind=IntentKind.FUERA_DE_ALCANCE, source_text=clause))
            continue
        if _HYPOTHETICAL.search(clause):
            intents.append(
                _from_clause(
                    IntentKind.HIPOTETICA,
                    clause,
                    product=_product_phrase(clause),
                    branches=branches,
                )
            )
            continue
        if _REMOVE.search(clause):
            intents.append(
                _from_clause(
                    IntentKind.QUITAR, clause, product=_product_phrase(clause), branches=branches
                )
            )
            continue
        if _MODIFY.search(_normalize(clause)) or re.search(r"\blos?\s+\w+\s+a\s+\d+", clause, re.I):
            intents.append(
                _from_clause(
                    IntentKind.MODIFICAR_CANTIDAD,
                    clause,
                    product=_product_phrase(clause),
                    branches=branches,
                )
            )
            continue
        if _STOCK.search(clause):
            intents.append(
                _from_clause(
                    IntentKind.CONSULTAR_STOCK,
                    clause,
                    product=_product_phrase(clause),
                    branches=branches,
                )
            )
            continue
        if _SUMMARY.search(clause):
            intents.append(Intent(kind=IntentKind.VER_RESUMEN_TOTAL, source_text=clause))
            continue
        if _PROJECT.search(clause):
            dimensions = _DIMENSIONS.search(clause)
            project = ProjectEntities(
                length_m=Decimal(dimensions.group(1).replace(",", ".")) if dimensions else None,
                width_m=Decimal(dimensions.group(2).replace(",", ".")) if dimensions else None,
                purpose="corral para ganado" if "corral" in normalized else None,
                whole_surface=True if "toda la superficie" in normalized else None,
            )
            intents.append(
                Intent(kind=IntentKind.ASESORIA_PROYECTO, project=project, source_text=clause)
            )
            continue
        if _POLICY.search(clause):
            policies = []
            if re.search(r"\b(?:pagar|pago|tarjeta|efectivo)\b", clause, re.I):
                policies.append("pagos")
            if re.search(r"\b(?:recoger|recojo|recogida|retiro)\b", clause, re.I):
                policies.append("recogida")
            if re.search(r"\b(?:domicilio|envio|entrega)\b", clause, re.I):
                policies.append("domicilio")
            if re.search(r"\bhorario\b", clause, re.I):
                policies.append("horarios")
            intents.extend(
                Intent(
                    kind=IntentKind.CONSULTAR_POLITICA,
                    policy=item,
                    branch=resolved.id if (resolved := resolve_branch(clause, branches)) else None,
                    source_text=clause,
                )
                for item in policies or ["general"]
            )
            continue
        if _ADD.search(clause) or _quantity(clause) is not None:
            intents.append(
                _from_clause(
                    IntentKind.AGREGAR, clause, product=_product_phrase(clause), branches=branches
                )
            )
            continue
        intents.append(
            _from_clause(
                IntentKind.CONSULTAR_PRODUCTO,
                clause,
                product=_product_phrase(clause),
                branches=branches,
            )
        )
    if not intents:
        intents = [Intent(kind=IntentKind.FUERA_DE_ALCANCE, source_text=cleaned)]
    return IntentBatch(intents=tuple(intents))
