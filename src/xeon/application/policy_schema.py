"""Validated tenant policy, with absent values kept explicitly unknown."""

from pydantic import BaseModel, ConfigDict, Field


class DeliveryOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disponible: bool | None = None
    nota: str | None = None
    costo: str | None = None


class DeliveryPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recoger_en_sede: DeliveryOption | None = None
    domicilio: DeliveryOption | None = None


class HoursPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lunes_a_viernes: str | None = None
    sabado: str | None = None
    domingo: str | None = None


class StorePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    demo: bool = False
    pagos: list[str] | None = None
    entrega: DeliveryPolicy | None = None
    horario: HoursPolicy | None = None
    vigencia_cotizacion_dias: int | None = Field(default=None, gt=0)
    iva: str | None = None
    descuentos: str | None = None
    fuera_de_horario: str | None = None
    facturacion: str | None = None
    # Identidad de la tienda para el PDF del borrador; ausentes se muestran como pendientes.
    nombre_comercial: str | None = None
    nit: str | None = None
    direccion: str | None = None
    telefono_tienda: str | None = None
