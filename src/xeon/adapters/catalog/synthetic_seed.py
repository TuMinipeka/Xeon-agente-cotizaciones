from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from xeon.domain.money import Money
from xeon.domain.product import Product, ProductId

SYNTHETIC_CATALOG_SIZE = 2_000
SYNTHETIC_CATALOG_VERSION = "synthetic-2026-10-17"
SYNTHETIC_SOURCE = "synthetic-ferreteria-demo-xeon"


@dataclass(frozen=True, slots=True)
class ProductFamilySeed:
    code: str
    name: str
    unit: str
    base_price: int
    price_step: int
    aliases: tuple[str, ...]
    context: str
    specs: tuple[tuple[str, str], ...]


def product(
    sku: str,
    name: str,
    unit: str,
    amount: str | Decimal,
    aliases: tuple[str, ...],
    *,
    specs: tuple[tuple[str, str], ...] = (),
    description_context: str = "",
) -> Product:
    return Product(
        id=ProductId(sku),
        name=name,
        unit=unit,
        list_price=Money(amount, "COP"),
        aliases=aliases,
        source=SYNTHETIC_SOURCE,
        catalog_version=SYNTHETIC_CATALOG_VERSION,
        specs=specs,
        description_context=description_context,
    )


CORE_SYNTHETIC_PRODUCTS: tuple[Product, ...] = (
    product(
        "CEM-50",
        "Cemento gris 50 kg",
        "bulto",
        "28900.00",
        ("cemento", "cemento 50kg", "bulto de cemento"),
        specs=(
            ("peso_kg", "50"),
            ("tipo", "uso general y estructural"),
            ("norma", "NTC 121"),
        ),
        description_context=(
            "Cemento gris para concreto, mortero, fundir placa, pegar ladrillo, "
            "bloque, repello, panete, piso y obra gris."
        ),
    ),
    product(
        "ALA-14",
        "Alambre de pua calibre 14",
        "metro",
        "1850.00",
        ("alambre", "alambre de pua", "alambre calibre 14"),
        specs=(
            ("calibre", "14"),
            ("recubrimiento", "galvanizado"),
            ("uso", "cercas ganaderas y linderos"),
        ),
        description_context=(
            "Alambre de puas para cercar finca, potrero, ganado, lotes y cerramiento rural."
        ),
    ),
    product(
        "TUB-PVC-20",
        "Tubo PVC presion 1/2 pulgada",
        "unidad",
        "4200.00",
        ("tubo pvc", "tubo 1/2"),
        specs=(
            ("diametro", "1/2 pulgada"),
            ("diametro_mm", "20"),
            ("presion_psi", "200"),
            ("fluido", "agua fria a presion"),
        ),
        description_context="Tubo para agua fria a presion, plomeria, bano, cocina y acueducto.",
    ),
    product(
        "MAN-AC-58",
        "Manguera de desague para aire acondicionado 5/8 pulgada",
        "metro",
        "2600.00",
        ("manguera desague aire acondicionado", "desague de aire", "manguera aire"),
        specs=(("diametro", "5/8 pulgada"), ("uso", "drenaje de condensado")),
        description_context=(
            "Manguera flexible para evacuar agua de condensacion y desague de aire acondicionado."
        ),
    ),
    product(
        "LAM-ZIN-26-244",
        "Lamina de zinc calibre 26 de 2,44 m",
        "lamina",
        "58900.00",
        ("lamina zinc calibre 26", "zinc 26 2.44"),
        specs=(
            ("calibre", "26"),
            ("largo_m", "2.44"),
            ("unidad_venta", "lamina completa"),
        ),
        description_context="Cubierta prefabricada galvanizada para techo y cerramiento.",
    ),
    product(
        "LAM-ZIN-28-244",
        "Lamina de zinc calibre 28 de 2,44 m",
        "lamina",
        "52900.00",
        ("lamina zinc calibre 28", "zinc 28 2.44"),
        specs=(
            ("calibre", "28"),
            ("largo_m", "2.44"),
            ("unidad_venta", "lamina completa"),
        ),
        description_context="Cubierta prefabricada galvanizada para techo de casa y cerramiento.",
    ),
    product(
        "LAM-ZIN-30-244",
        "Lamina de zinc calibre 30 de 2,44 m",
        "lamina",
        "47900.00",
        ("lamina zinc calibre 30", "zinc 30 2.44"),
        specs=(
            ("calibre", "30"),
            ("largo_m", "2.44"),
            ("unidad_venta", "lamina completa"),
        ),
        description_context="Cubierta prefabricada galvanizada liviana para techo.",
    ),
)

# Additional core references are kept outside the frozen 2,000-item evaluation
# seed so the independent fixture snapshot remains reproducible.
ADDITIONAL_CORE_PRODUCTS: tuple[Product, ...] = (
    product(
        "PAL-RED-FIB",
        "Pala redonda mango de fibra",
        "unidad",
        "43700.00",
        ("pala redonda de fibra", "pala redonda mango de fibra"),
        specs=(("forma", "redonda"), ("mango", "fibra")),
        description_context="Pala redonda de mango de fibra para tierra, arena y mezcla.",
    ),
    product(
        "PAL-CUA-MAD",
        "Pala cuadrada mango de madera",
        "unidad",
        "39800.00",
        ("pala cuadrada de madera", "pala cuadrada mango de madera"),
        specs=(("forma", "cuadrada"), ("mango", "madera")),
        description_context="Pala cuadrada de mango de madera para recoger materiales.",
    ),
)


def _family(
    code: str,
    name: str,
    unit: str,
    price: int,
    aliases: tuple[str, ...],
    context: str,
    *,
    specs: tuple[tuple[str, str], ...] = (),
) -> ProductFamilySeed:
    return ProductFamilySeed(
        code, name, unit, price, max(price // 120, 10), aliases, context, specs
    )


FAMILY_SEEDS: tuple[ProductFamilySeed, ...] = (
    _family("CEM", "Cemento gris", "bulto", 27_000, ("cemento",), "concreto mortero placa piso"),
    _family("MOR", "Mortero seco", "bulto", 24_000, ("mortero",), "ladrillo bloque panete repello"),
    _family(
        "LAD", "Ladrillo estructural", "unidad", 1_300, ("ladrillo",), "muro pared mamposteria"
    ),
    _family("BLO", "Bloque de concreto", "unidad", 2_900, ("bloque",), "muro pared cerramiento"),
    _family(
        "VAR", "Varilla corrugada", "unidad", 18_000, ("varilla",), "refuerzo placa columna viga"
    ),
    _family(
        "MAL", "Malla electrosoldada", "unidad", 72_000, ("malla",), "refuerzo placa piso concreto"
    ),
    _family(
        "LAM",
        "Lamina galvanizada",
        "lamina",
        42_000,
        ("lamina", "zinc"),
        "techo cubierta casa",
        specs=(("unidad_venta", "lamina completa"),),
    ),
    _family("TEJ", "Teja de fibrocemento", "unidad", 39_000, ("teja",), "techo cubierta vivienda"),
    _family("TOR", "Tornillo galvanizado", "caja", 8_000, ("tornillo",), "fijacion madera metal"),
    _family("CLA", "Clavo de acero", "libra", 5_500, ("clavo",), "fijacion madera formaleta"),
    _family(
        "PIN", "Pintura arquitectonica", "galon", 54_000, ("pintura",), "pared interior exterior"
    ),
    _family("BRO", "Brocha profesional", "unidad", 7_500, ("brocha",), "pintura esmalte barniz"),
    _family("ROD", "Rodillo para pintura", "unidad", 12_000, ("rodillo",), "pintar pared techo"),
    _family("TUP", "Tubo PVC presion", "unidad", 5_000, ("tubo pvc",), "agua fria plomeria"),
    _family("TUS", "Tubo PVC sanitario", "unidad", 8_500, ("tubo sanitario",), "desague sanitario"),
    _family("ACP", "Accesorio PVC", "unidad", 1_600, ("accesorio pvc",), "union codo plomeria"),
    _family("MAN", "Manguera flexible", "metro", 2_200, ("manguera",), "agua riego jardin finca"),
    _family("CAB", "Cable electrico", "metro", 1_900, ("cable",), "instalacion electrica vivienda"),
    _family(
        "BRE",
        "Interruptor termomagnetico",
        "unidad",
        21_000,
        ("breaker",),
        "proteccion circuito tablero",
    ),
    _family(
        "TOM", "Tomacorriente", "unidad", 9_000, ("tomacorriente",), "enchufe instalacion electrica"
    ),
    _family("BOM", "Bombillo LED", "unidad", 8_500, ("bombillo",), "iluminacion casa bodega"),
    _family("MAR", "Martillo", "unidad", 24_000, ("martillo",), "golpear clavar carpinteria"),
    _family("DES", "Destornillador", "unidad", 9_500, ("destornillador",), "ajustar tornillo"),
    _family("LLA", "Llave ajustable", "unidad", 28_000, ("llave",), "tuerca plomeria mecanica"),
    _family(
        "TAL", "Taladro percutor", "unidad", 185_000, ("taladro",), "perforar concreto metal madera"
    ),
    _family(
        "BRQ", "Broca multiproposito", "unidad", 6_500, ("broca",), "perforar concreto metal madera"
    ),
    _family("DIS", "Disco de corte", "unidad", 7_000, ("disco",), "cortar metal concreto pulidora"),
    _family("SOL", "Electrodo para soldadura", "kilogramo", 16_000, ("electrodo",), "soldar acero"),
    _family("PAL", "Pala", "unidad", 42_000, ("pala",), "tierra arena mezcla agricultura"),
    _family("MAC", "Machete", "unidad", 31_000, ("machete",), "roceria finca campo"),
    _family("ALA", "Alambre de pua", "rollo", 96_000, ("alambre",), "cerca ganado potrero"),
    _family(
        "CER",
        "Malla para cerramiento",
        "rollo",
        118_000,
        ("malla cerramiento",),
        "lote jardin corral",
    ),
    _family("RIE", "Aspersor de riego", "unidad", 17_000, ("aspersor",), "riego cultivo jardin"),
    _family("BAG", "Bomba de agua", "unidad", 210_000, ("bomba",), "tanque pozo riego"),
    _family(
        "PEG",
        "Adhesivo para construccion",
        "unidad",
        13_000,
        ("pegante",),
        "baldosa ceramica madera",
    ),
    _family("SIL", "Silicona selladora", "unidad", 15_000, ("silicona",), "ventana bano cocina"),
    _family("CRR", "Cerradura", "unidad", 39_000, ("cerradura",), "puerta seguridad vivienda"),
    _family("BIS", "Bisagra", "par", 8_000, ("bisagra",), "puerta mueble ventana"),
    _family("BAL", "Baldosa ceramica", "caja", 52_000, ("baldosa",), "piso pared bano cocina"),
    _family("BOT", "Bota de trabajo", "par", 68_000, ("bota",), "proteccion obra finca"),
)


def build_synthetic_products() -> tuple[Product, ...]:
    """Build exactly 2,000 deterministic demo references, never real commercial data."""

    products = list(CORE_SYNTHETIC_PRODUCTS)
    variants = [0] * len(FAMILY_SEEDS)
    cursor = 0
    while len(products) < SYNTHETIC_CATALOG_SIZE:
        family_position = cursor % len(FAMILY_SEEDS)
        family = FAMILY_SEEDS[family_position]
        variants[family_position] += 1
        variant = variants[family_position]
        cursor += 1
        reference = f"referencia sintetica {variant}"
        products.append(
            product(
                f"SYN-{family.code}-{cursor:04d}",
                f"{family.name} {reference}",
                family.unit,
                Decimal(family.base_price + family.price_step * variant),
                tuple(f"{alias} {reference}" for alias in family.aliases),
                specs=(
                    *family.specs,
                    ("categoria", family.name.casefold()),
                    ("referencia_sintetica", str(variant)),
                ),
                description_context=(
                    f"{family.context}. Producto ficticio para pruebas de XEON; "
                    "no es una referencia comercial real."
                ),
            )
        )
    return tuple(products)


SYNTHETIC_PRODUCTS = build_synthetic_products()
SYNTHETIC_QUOTE_NOTE = "Datos sinteticos de Ferreteria Demo XEON. No atribuir a una empresa real."
