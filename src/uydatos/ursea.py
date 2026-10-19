"""Precio de paridad de importación (PPI) de los combustibles, de URSEA, y su comparación con ANCAP.

El PPI es lo que costaría poner el combustible importado en una planta de distribución de Uruguay:
precio internacional, flete, seguro, puerto, almacenaje, costos financieros y margen del importador.
URSEA lo calcula todos los meses. Comparado con el precio ex planta de ANCAP responde una pregunta
que está siempre en el debate público: **¿ANCAP vende por encima o por debajo de lo que costaría
importar?**

Las fuentes (catálogo de datos abiertos)
----------------------------------------
- `ursea-ppi_vs_pe_v2`, recurso «Precios hasta planta de distribución (sin FO bajo S)»
  (`ppi_da_nuevo.csv`): el PPI mensual en $/litro, desde la ventana 26/09/2021–25/10/2021.
- `ursea-componentes_del_ppi_de_combustibles`: el desglose de cada mes en USD/m³, desde el FOB hasta
  el precio con impuestos, para las gasolinas, los gasoils y el GLP, desde el cierre del 25/10/2020.
- `ancap-precio-combustible-ex-planta`: el precio ex planta de ANCAP, mensual, en $/litro o $/kg.

Las trampas (medidas el 11/10/2026)
-----------------------------------
1. **El recurso «PPI al consumidor final» (2002–2020) fue pisado**: `ppi_pe.csv` es idéntico byte a
   byte al archivo de componentes (sha256 `fbf0132c…`). La serie histórica al consumidor ya no está
   en el catálogo. Este módulo no la lee.
2. **Hay tres modelos de PPI y no se empalman**: al consumidor final (2002-01 a 2020-09), hasta planta
   «con FO bajo S» (13 meses, 2020-10 a 2021-10, con fechas `d/m/aaaa`) y hasta planta «sin FO bajo S»
   (el vigente, con fechas ISO). Se lee sólo el vigente.
3. **Con impuestos y sin impuestos no se mezclan.** El precio ex planta de ANCAP es el de venta al
   público **menos** fletes, márgenes **e impuestos** (lo dice el dataset). Se compara con el PPI sin
   impuestos y con la mezcla de agrocombustibles (`_ExP_AC`, el «subtotal 3»), que es el producto que
   ANCAP vende. Compararlo con el PPI con impuestos, o el precio de surtidor con el PPI ex planta,
   inventa una brecha.
4. **El PPI de una ventana rige el mes siguiente.** La ventana 26/07–25/08 tiene «fecha de vigencia»
   01/09 en 353 de 355 filas de componentes; en las otras 2 (el último cierre de Gas Oil 10S y de GLP)
   la vigencia publicada repite el mes anterior, y quedan dos PPI vigentes el mismo mes. La vigencia se
   calcula del cierre y la publicada distinta se declara.
5. **Un nombre de columna miente**: `FuelP_ExP` es, según la metadata, el PPI **con impuestos** del
   fuel oil pesado, aunque su nombre diga «ex planta» como los sin impuestos.
6. **El GLP no se compara**: el PPI lo da en $/litro y ANCAP en $/kg. Sin la densidad de cada mes,
   restarlos no tiene sentido.
7. **El archivo ex planta de ANCAP es un registro acumulado**: 19.105 filas para 1.204 pares
   mes-producto, en dos bloques separados por una línea vacía, con **tres formatos de fecha**
   (`2026-08`, `202,608` —el año-mes con una coma de miles— y `202301`). Las repeticiones iguales se
   unen; **93 pares tienen valores distintos** (todos de Supergas, Supergas a granel y Propano
   industrial, incluido un `-26,93` contra un `0`): esos quedan en nulo y se listan en `conflictos`.
   Las gasolinas y los gasoils no tienen ninguno y están completos de 2022-01 a 2026-08.
8. Los componentes cierran: `total_precio_ex_planta_2` ($/l) = `total_precio_ex_planta_1` (USD/m³)
   × tipo de cambio ÷ 1000 en las 355 filas, con diferencia menor a 0,02. Una fila que no cierre se
   rechaza.
9. **Una ventana del PPI termina antes de empezar**: `2022-12-26` a `2022-12-25` (casi seguro
   `2023-01-25`). No se corrige: se descarta, se lista en `descartadas` y ese mes queda sin
   comparación. Otra ventana dura 21 días (`2024-02-26` a `2024-03-18`) y es real: va con `dias`.

Uso:
    python -m uydatos.ursea bajar datos/
    python -m uydatos.ursea comparar datos/ "Gasoil 50-S"
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Optional, Sequence

from uydatos import red
from uydatos.errores import DatosInvalidos

# clave -> (dataset del catálogo, nombre del archivo CSV dentro del dataset). La URL se resuelve
# por el catálogo al bajar: el dataset del PPI tiene seis recursos de tres modelos distintos, y el
# que importa se reconoce por el nombre del archivo, no por el orden.
ARCHIVOS = {
    "ppi": ("ursea-ppi_vs_pe_v2", "ppi_da_nuevo.csv"),
    "componentes": ("ursea-componentes_del_ppi_de_combustibles", "componentes-del-ppi-de-gasolinas-gasoils-y-glp.csv"),
    "ex_planta": ("ancap-precio-combustible-ex-planta", "datos-de-precios-de-combustibles-ex-planta.csv"),
}

COLUMNAS_PPI = [
    "Inicio", "Fin",
    "Premium_ExP", "Premium_ExP_AC", "Premium_ExP_imp",
    "Super_ExP", "Super_ExP_AC", "Super_ExP_imp",
    "Gasoil50S_ExP", "Gasoil50S_ExP_AC", "F_Gasoil50S", "Gasoil50S_ExP_imp",
    "Gasoil10S_ExP", "Gasoil10S_ExP_AC", "F_Gasoil10S", "Gasoil10S_ExP_imp",
    "GLP_PD", "GLP_PD_imp", "Propano_PD", "Propano_PD_imp",
    "FuelM_PD", "FuelM_ExP_imp", "FuelP_PD", "FuelP_ExP",
    "Etanol", "Biodiesel",
]  # fmt: skip
# producto -> (sin impuestos, sin impuestos con agrocombustibles, con impuestos), en $/l
PRODUCTOS_PPI: dict[str, tuple[Optional[str], Optional[str], Optional[str]]] = {
    "Gasolina Premium 97": ("Premium_ExP", "Premium_ExP_AC", "Premium_ExP_imp"),
    "Gasolina Super 95": ("Super_ExP", "Super_ExP_AC", "Super_ExP_imp"),
    "Gasoil 50-S": ("Gasoil50S_ExP", "Gasoil50S_ExP_AC", "Gasoil50S_ExP_imp"),
    "Gasoil 10-S": ("Gasoil10S_ExP", "Gasoil10S_ExP_AC", "Gasoil10S_ExP_imp"),
    "GLP": ("GLP_PD", None, "GLP_PD_imp"),
    "Propano": ("Propano_PD", None, "Propano_PD_imp"),
    "Fuel Oil Medio": ("FuelM_PD", None, "FuelM_ExP_imp"),
    "Fuel Oil Pesado": ("FuelP_PD", None, "FuelP_ExP"),  # trampa 5: FuelP_ExP es con impuestos
    "Etanol": (None, None, "Etanol"),
    "Biodiesel": (None, None, "Biodiesel"),
}
# Los que se comparan con ANCAP: mismo nombre en los dos archivos y la misma unidad ($/l).
COMPARABLES = ("Gasolina Super 95", "Gasolina Premium 97", "Gasoil 50-S", "Gasoil 10-S")

COLUMNAS_EX_PLANTA = ["Año-Mes", "Producto", "Unidad", "PrecioExPlantaUYU"]
TOLERANCIA_TOTAL = 0.02


class UrseaInvalido(DatosInvalidos):
    """El archivo no cumple el contrato medido."""


def _numero(texto: str, donde: str) -> float:
    t = texto.strip()
    try:
        return float(t.replace(",", ".")) if t.count(",") == 1 and "." not in t else float(t)
    except ValueError:
        raise UrseaInvalido(f"{donde}: {texto!r} no es un número") from None


def _mes_siguiente(d: date) -> str:
    return f"{d.year + (d.month == 12)}-{d.month % 12 + 1:02d}"


def _encabezado(fila: list[str]) -> list[str]:
    return [c.replace("\ufeff", "").strip() for c in fila]


# --- El PPI -------------------------------------------------------------------------------------


def leer_ppi(ruta: Path) -> list[dict]:
    """El PPI vigente, una fila por ventana y producto, en $/litro. No sale a la red.

    Cada fila: `inicio`, `fin` (la ventana de cálculo), `vigencia` (`AAAA-MM`, el mes siguiente al
    fin), `producto`, `sin_impuestos`, `sin_impuestos_con_agro` y `con_impuestos` (`None` donde el
    producto no tiene esa columna), y `dias` (el largo de la ventana). Devuelve `{"filas",
    "descartadas"}`: una ventana que termina antes de empezar no se corrige, se descarta y se lista
    (trampa 9). Rechaza otras columnas, una fecha que no sea ISO —el modelo viejo usaba `d/m/aaaa`— y
    dos ventanas con la misma vigencia.
    """
    ruta = Path(ruta)
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        lector = csv.reader(f)
        encabezado = _encabezado(next(lector, []))
        if encabezado != COLUMNAS_PPI:
            raise UrseaInvalido(f"{ruta}: columnas {encabezado}, se esperaban {COLUMNAS_PPI}")
        filas, vistas, descartadas = [], set(), []
        for n, campos in enumerate(lector, start=2):
            if not any(c.strip() for c in campos):
                continue
            if len(campos) != len(COLUMNAS_PPI):
                raise UrseaInvalido(f"{ruta} fila {n}: {len(campos)} columnas")
            d = dict(zip(COLUMNAS_PPI, campos))
            try:
                inicio, fin = date.fromisoformat(d["Inicio"]), date.fromisoformat(d["Fin"])
            except ValueError:
                raise UrseaInvalido(
                    f"{ruta} fila {n}: fechas {d['Inicio']!r}, {d['Fin']!r} no son AAAA-MM-DD"
                ) from None
            if fin < inicio:
                descartadas.append({"fila": n, "inicio": inicio.isoformat(), "fin": fin.isoformat()})
                continue
            vigencia = _mes_siguiente(fin)
            if vigencia in vistas:
                raise UrseaInvalido(f"{ruta} fila {n}: otra ventana ya rige en {vigencia}")
            vistas.add(vigencia)
            for producto, columnas in PRODUCTOS_PPI.items():
                sin, agro, con = (_numero(d[c], f"{ruta} fila {n}") if c else None for c in columnas)
                filas.append(
                    {
                        "inicio": inicio.isoformat(),
                        "fin": fin.isoformat(),
                        "vigencia": vigencia,
                        "dias": (fin - inicio).days + 1,
                        "producto": producto,
                        "sin_impuestos": sin,
                        "sin_impuestos_con_agro": agro,
                        "con_impuestos": con,
                    }
                )
    if not filas:
        raise UrseaInvalido(f"{ruta}: archivo sin filas de datos")
    return {"filas": filas, "descartadas": descartadas}


# --- Los componentes ----------------------------------------------------------------------------


def leer_componentes(ruta: Path) -> list[dict]:
    """El desglose de cada PPI, en USD/m³, salvo `tipo_cambio_promedio` y `total_precio_ex_planta_2` ($/l).

    Cada fila trae todas las columnas del archivo como número, más `vigencia` (calculada: el mes
    siguiente al cierre) y `vigencia_publicada` (la del archivo, `AAAA-MM`): si no coinciden, la fila
    tiene el error de la trampa 4. Rechaza la fila cuyo total en pesos no cierre con el total en
    dólares por el tipo de cambio.
    """
    ruta = Path(ruta)
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        lector = csv.DictReader(f)
        requeridas = {"producto", "fecha_cierre", "fecha_vigencia", "total_precio_ex_planta_1"}
        requeridas |= {
            "tipo_cambio_promedio",
            "total_precio_ex_planta_2",
            "subtotal_3_precio_ex_planta_con_biocombustible",
        }
        faltan = requeridas - set(lector.fieldnames or [])
        if faltan:
            raise UrseaInvalido(f"{ruta}: faltan las columnas {sorted(faltan)}")
        filas = []
        for n, d in enumerate(lector, start=2):
            donde = f"{ruta} fila {n}"
            try:
                cierre, vig = date.fromisoformat(d["fecha_cierre"]), date.fromisoformat(d["fecha_vigencia"])
            except ValueError:
                raise UrseaInvalido(f"{donde}: fechas que no son AAAA-MM-DD") from None
            fila: dict = {"producto": d["producto"].strip(), "fecha_cierre": cierre.isoformat()}
            for k, v in d.items():
                if k not in ("producto", "fecha_cierre", "fecha_vigencia"):
                    fila[k] = _numero(v, donde)
            usd, tc, pesos = (
                fila["total_precio_ex_planta_1"],
                fila["tipo_cambio_promedio"],
                fila["total_precio_ex_planta_2"],
            )
            if abs(usd * tc / 1000 - pesos) > TOLERANCIA_TOTAL:
                raise UrseaInvalido(f"{donde}: {usd} USD/m³ × {tc} / 1000 no da {pesos} $/l")
            fila["vigencia"] = _mes_siguiente(cierre)
            fila["vigencia_publicada"] = f"{vig.year}-{vig.month:02d}"
            filas.append(fila)
    if not filas:
        raise UrseaInvalido(f"{ruta}: archivo sin filas de datos")
    return filas


# --- El ex planta de ANCAP ----------------------------------------------------------------------


def _mes_ancap(texto: str, donde: str) -> str:
    """`2026-08`, `202,608` y `202608` son el mismo mes (trampa 7)."""
    t = texto.strip().replace(",", "")
    if len(t) == 7 and t[4] == "-":
        t = t[:4] + t[5:]
    if len(t) != 6 or not t.isdigit() or not 1 <= int(t[4:]) <= 12:
        raise UrseaInvalido(f"{donde}: {texto!r} no es un año-mes")
    return f"{t[:4]}-{t[4:]}"


def leer_ex_planta(ruta: Path) -> dict:
    """El precio ex planta de ANCAP por mes y producto, sin repeticiones. No sale a la red.

    Devuelve `precios` (`{(mes, producto): {"valor", "unidad"}}`, con `valor` en `None` si el
    archivo publica dos valores distintos), `conflictos` (esos pares con los valores publicados),
    `filas` y `repetidas` (filas iguales a otra ya leída).
    """
    ruta = Path(ruta)
    vistos: dict[tuple[str, str], set[tuple[float, str]]] = defaultdict(set)
    filas = 0
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        lector = csv.reader(f, delimiter=";")
        encabezado = _encabezado(next(lector, []))
        if encabezado != COLUMNAS_EX_PLANTA:
            raise UrseaInvalido(f"{ruta}: columnas {encabezado}, se esperaban {COLUMNAS_EX_PLANTA}")
        for n, campos in enumerate(lector, start=2):
            if not any(c.strip() for c in campos):
                continue  # la línea vacía entre los dos bloques
            if len(campos) != 4:
                raise UrseaInvalido(f"{ruta} fila {n}: {len(campos)} columnas")
            mes = _mes_ancap(campos[0], f"{ruta} fila {n}")
            valor = _numero(campos[3].replace(".", ""), f"{ruta} fila {n}")
            vistos[(mes, campos[1].strip())].add((valor, campos[2].strip()))
            filas += 1
    if not vistos:
        raise UrseaInvalido(f"{ruta}: archivo sin filas de datos")
    precios, conflictos = {}, []
    for clave, valores in sorted(vistos.items()):
        unidades = {u for _, u in valores}
        if len(valores) == 1:
            ((valor, unidad),) = valores
            precios[clave] = {"valor": valor, "unidad": unidad}
        else:
            precios[clave] = {"valor": None, "unidad": unidades.pop() if len(unidades) == 1 else ""}
            conflictos.append({"mes": clave[0], "producto": clave[1], "valores": sorted(v for v, _ in valores)})
    return {
        "precios": precios,
        "conflictos": conflictos,
        "filas": filas,
        "repetidas": filas - sum(map(len, vistos.values())),
    }


# --- La comparación -----------------------------------------------------------------------------


def comparar(ppi: dict, ex_planta: dict, producto: str) -> list[dict]:
    """ANCAP ex planta contra el PPI sin impuestos con agrocombustibles, mes a mes. No sale a la red.

    El mes es el de vigencia del PPI (la ventana que cerró el 25 del mes anterior). Cada fila:
    `mes`, `ancap_ex_planta`, `ppi`, `diferencia` ($/l) y `diferencia_pct` (positiva = ANCAP por
    encima de la paridad). Un mes sin los dos precios no aparece: no se rellena.
    """
    if producto not in COMPARABLES:
        raise UrseaInvalido(f"{producto!r} no se compara: los comparables son {list(COMPARABLES)}")
    por_mes = {p["vigencia"]: p["sin_impuestos_con_agro"] for p in ppi["filas"] if p["producto"] == producto}
    salida = []
    for mes in sorted(por_mes):
        anc = ex_planta["precios"].get((mes, producto))
        if anc is None or anc["valor"] is None or por_mes[mes] is None:
            continue
        if anc["unidad"] != "$/lt":
            raise UrseaInvalido(f"{producto} {mes}: ANCAP lo da en {anc['unidad']!r} y el PPI en $/l")
        dif = anc["valor"] - por_mes[mes]
        salida.append(
            {
                "mes": mes,
                "ancap_ex_planta": anc["valor"],
                "ppi": por_mes[mes],
                "diferencia": round(dif, 2),
                "diferencia_pct": round(100 * dif / por_mes[mes], 1),
            }
        )
    return salida


def url_de(recursos: list[dict], archivo: str) -> str:
    """La URL del recurso cuyo archivo se llama `archivo`. No sale a la red."""
    urls = [r["url"] for r in recursos if r["url"].rsplit("/", 1)[-1] == archivo]
    if len(urls) != 1:
        raise UrseaInvalido(f"{archivo}: {len(urls)} recursos con ese nombre en el dataset, se esperaba 1")
    return urls[0]


def descargar(destino: Path) -> dict[str, Path]:
    """Baja los tres archivos a la carpeta `destino`, resolviendo cada URL por el catálogo.

    **Sale a la red.** Los guarda con el nombre del archivo publicado.
    """
    from uydatos import catalogo

    destino = Path(destino)
    salida = {}
    for clave, (dataset, archivo) in ARCHIVOS.items():
        salida[clave] = red.bajar(url_de(catalogo.recursos(dataset), archivo), destino / archivo)
    return salida


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m uydatos.ursea", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="orden", required=True)
    b = sub.add_parser("bajar")
    b.add_argument("carpeta", type=Path)
    c = sub.add_parser("comparar")
    c.add_argument("carpeta", type=Path)
    c.add_argument("producto", choices=COMPARABLES)
    args = ap.parse_args(argv)
    if args.orden == "bajar":
        for k, p in descargar(args.carpeta).items():
            print(f"{k}: {p}")
        return 0
    ppi = leer_ppi(args.carpeta / ARCHIVOS["ppi"][1])
    ex = leer_ex_planta(args.carpeta / ARCHIVOS["ex_planta"][1])
    print(f"{args.producto}: ANCAP ex planta contra el PPI sin impuestos con agrocombustibles ($/l)")
    print("mes;ancap;ppi;diferencia;%")
    for f in comparar(ppi, ex, args.producto):
        print(f"{f['mes']};{f['ancap_ex_planta']};{f['ppi']};{f['diferencia']};{f['diferencia_pct']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
