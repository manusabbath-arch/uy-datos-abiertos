"""Precios máximos de combustibles de ANCAP, aprobados por decreto del Poder Ejecutivo.

Dataset `ancap-precio-combustible-pe` del catálogo de datos abiertos: **precio máximo al
público, IVA incluido**. **No es** `ancap-precio-combustible-ex-planta`, que es el precio
deducidos flete, tasas y margen. Los dos se citan como "los precios de ANCAP" y no son el mismo
número.

Las trampas (medidas en octubre de 2026)
---------------------------------------
1. **Las columnas vienen invertidas.** El encabezado dice `Unidad` y `Valor`, pero `Unidad`
   trae el **número** y `Valor` la **unidad de medida**. Quien sume "Valor" suma `'$/lt'`.
   Si la fuente las vuelve a dar vuelta, el lector lo rechaza.
2. **El archivo no es una serie: es un log de publicaciones acumulativas.** Cada mes ANCAP
   republica el año entero hasta ese mes y el archivo **apila** las publicaciones: un mismo mes
   aparece decenas de veces. Contar o promediar filas mide publicaciones, no precios: usar
   `serie_mensual()`.
3. **El BOM viene doble**: abrir con `utf-8-sig` no alcanza, queda un `\\ufeff` pegado al
   nombre de la primera columna.
4. **`S/C`** es *sin cotización*: un nulo, no un cero.
5. **Coma decimal y punto de miles** (`1.234,50`): un `float()` pelado no sirve.

Uso:
    python -m uydatos.ancap bajar precios.csv
    python -m uydatos.ancap serie precios.csv "GASOIL 50-S *"
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Optional, Sequence

from uydatos import red

DATASET = "ancap-precio-combustible-pe"
URL_CSV = (
    "https://catalogodatos.gub.uy/dataset/556beb30-02fc-4d06-909a-f42083c89ef7/resource/"
    "1a37fc4a-44fd-4842-bcb4-b5845dc8eced/download/datos-de-precios-de-combustibles.csv"
)

COLUMNAS_ESPERADAS = ["Año", "Mes", "Producto", "Unidad", "Valor"]
SIN_COTIZACION = "S/C"


class AncapInvalido(ValueError):
    """La serie no cumple el contrato de la fuente."""


def numero_europeo(texto: str) -> Optional[float]:
    """`'1.234,50'` -> 1234.5. `None` si no se puede leer: nunca un cero inventado."""
    t = texto.replace("\xa0", " ").strip().replace(".", "").replace(",", ".")
    if not t:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def _limpiar_encabezado(campos: list[str]) -> list[str]:
    return [c.replace("﻿", "").strip() for c in campos]


def leer_publicaciones(ruta: Path) -> list[dict]:
    """Lee el archivo **crudo**: una fila por publicación, sin deduplicar.

    Devuelve, por fila, `anio`, `mes`, `producto`, `precio` (float | None) y `unidad`.
    Para el precio de un mes usar `serie_mensual()`, no esto.
    """
    ruta = Path(ruta)
    if not ruta.is_file():
        raise AncapInvalido(f"{ruta}: el archivo no está en el disco")
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        lector = csv.reader(f, delimiter=";")
        try:
            encabezado = _limpiar_encabezado(next(lector))
        except StopIteration:
            raise AncapInvalido(f"{ruta}: archivo vacío") from None
        if encabezado != COLUMNAS_ESPERADAS:
            raise AncapInvalido(f"{ruta}: columnas inesperadas {encabezado}, se esperaban {COLUMNAS_ESPERADAS}")
        publicaciones = []
        for n, campos in enumerate(lector, start=2):
            if not any(c.strip() for c in campos):
                continue
            if len(campos) != len(COLUMNAS_ESPERADAS):
                raise AncapInvalido(f"{ruta} fila {n}: {len(campos)} columnas")
            anio_crudo, mes_crudo, producto, precio_crudo, unidad = (c.strip() for c in campos)
            # `Valor` tiene que traer la UNIDAD. Si trae un número, la fuente invirtió las columnas.
            if unidad and unidad != SIN_COTIZACION and not unidad.startswith("$"):
                raise AncapInvalido(
                    f"{ruta} fila {n}: la columna `Valor` debería traer la unidad y trae {unidad!r}. "
                    f"¿La fuente invirtió las columnas?"
                )
            try:
                anio, mes = int(anio_crudo), int(mes_crudo)
            except ValueError:
                raise AncapInvalido(f"{ruta} fila {n}: año/mes ilegible {campos[:2]!r}") from None
            if precio_crudo == SIN_COTIZACION:
                precio = None
            else:
                precio = numero_europeo(precio_crudo)
                if precio is None:
                    raise AncapInvalido(f"{ruta} fila {n}: precio ilegible {precio_crudo!r}")
            publicaciones.append(
                {
                    "anio": anio,
                    "mes": mes,
                    "producto": producto,
                    "precio": precio,
                    "unidad": "" if unidad == SIN_COTIZACION else unidad,
                }
            )
    if not publicaciones:
        raise AncapInvalido(f"{ruta}: archivo sin filas de datos")
    return publicaciones


def serie_mensual(publicaciones: list[dict]) -> list[dict]:
    """Deduplica el log apilado: **una fila por (producto, año, mes)**.

    Desempate declarado: **el valor manda sobre el `S/C`**. Un mes que alguna vez tuvo precio no
    se pierde porque una publicación posterior diga `S/C`; entre dos precios distintos gana el
    de la publicación más reciente (la que aparece después en el archivo).
    """
    orden: list[tuple] = []
    estado: dict[tuple, dict] = {}
    for p in publicaciones:
        clave = (p["producto"], p["anio"], p["mes"])
        if clave not in estado:
            orden.append(clave)
            estado[clave] = {
                "anio": p["anio"],
                "mes": p["mes"],
                "producto": p["producto"],
                "precio": None,
                "unidad": "",
            }
        if p["precio"] is not None:
            estado[clave]["precio"] = p["precio"]
            estado[clave]["unidad"] = p["unidad"]
    return [estado[k] for k in orden]


def precio_del_mes(serie: list[dict], producto: str, anio: int, mes: int) -> Optional[float]:
    """El precio de ese producto en ese mes, o `None` si nunca tuvo cotización.

    Espera la salida de `serie_mensual()`, no la de `leer_publicaciones()`.
    """
    for s in serie:
        if s["producto"] == producto and s["anio"] == anio and s["mes"] == mes:
            return s["precio"]
    return None


def descargar(destino: Path, url: str = URL_CSV) -> Path:
    """Baja el CSV del catálogo a `destino`. **Única función que sale a la red.**

    Si la URL del recurso cambia, `uydatos.catalogo.recursos(DATASET)` da la vigente.
    """
    return red.bajar(url, destino)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m uydatos.ancap", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="orden", required=True)
    b = sub.add_parser("bajar")
    b.add_argument("archivo", type=Path)
    s = sub.add_parser("serie", help="precio por mes de un producto (sin argumento: lista los productos)")
    s.add_argument("archivo", type=Path)
    s.add_argument("producto", nargs="?")
    args = ap.parse_args(argv)

    if args.orden == "bajar":
        print(f"bajado {descargar(args.archivo)}")
        return 0
    publicaciones = leer_publicaciones(args.archivo)
    serie = serie_mensual(publicaciones)
    print(f"{len(publicaciones)} publicaciones, {len(serie)} meses distintos (producto x año x mes)")
    if not args.producto:
        for p in sorted({s["producto"] for s in serie}):
            print(f"  {p}")
        return 0
    print("anio;mes;precio;unidad")
    for s in serie:
        if s["producto"] == args.producto:
            print(f"{s['anio']};{s['mes']:02d};{'' if s['precio'] is None else s['precio']};{s['unidad']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
