"""Cantidad de ventas de combustibles de ANCAP, por mercado, producto y mes.

Dataset `ancap-cantidad-ventas-combustibles` del catálogo de datos abiertos: **volúmenes**, no
precios. Es el denominador de mercado que le faltaba a `uydatos.ancap`, que trae los precios.

Las trampas (medidas en octubre de 2026 sobre el archivo de 1.200 filas, sha256 `2c648ef7…`)
---------------------------------------------------------------------------------------------
1. **La columna `Unidad` mezcla dos unidades.** 1.178 filas en `Miles de m3` y 22 en `Toneladas`
   —los `COMBUSTIBLES SÓLIDOS`, y sólo en el mercado INTERNO—. Sumar `CantidadCorregida` sin
   separarlas pone 12.330 al lado de 264.027: los dos parecen plausibles, así que el error no salta
   a la vista. `serie_mensual()` pide la unidad y `resumen()` las suma aparte, como las monedas de
   `uydatos.compras`: una unidad nueva suma en su propio renglón en vez de romper el archivo.
2. **Es una ventana móvil de cinco años, y los huecos no son sólo el año en curso.** Medido: 2022 y
   2023 completos, **2024 sin octubre**, **2025 sin agosto, setiembre ni octubre**, y 2026 hasta
   agosto. El hueco es global —todos los mercados y productos a la vez—, así que es de la
   publicación: un mes que no está no es un mes en cero.
3. **`QUEROSENO` y `QUEROSENOS` no son lo mismo**: el primero es de `BLANCOS` y el segundo de
   `SOLVENTES`. Dos nombres que parecen el error de tipeo del otro son productos de familias
   distintas: no se unifican.
4. **`Bandera` parte el mismo producto** en `B/E` y `B/N`. `ZONA FRANCA` (96 filas) y `Exportaciones`
   (9) son todo `B/E`; `UTE` (56) todo `B/N`; y `Bunker` viene mezclado (195 `B/E`, 170 `B/N`).
   Agrupar sin la bandera junta 168 de las 1.200 filas.
5. **Coma decimal** (`5,619439`), y `Mes`/`Anio` como texto con cero adelante (`'01'`, `'2026'`).
6. **Los negativos son correcciones, no errores**: 6 filas de 1.200, la más negativa `-0,160273`.
   Se leen y se suman.

Uso:
    python -m uydatos.ancap_ventas bajar ventas.csv
    python -m uydatos.ancap_ventas resumen ventas.csv
    python -m uydatos.ancap_ventas serie ventas.csv INTERNO "GAS OIL"
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional, Sequence

from uydatos import red
from uydatos.ancap import numero_europeo

DATASET = "ancap-cantidad-ventas-combustibles"
# URL de respaldo, por si el catálogo no responde. **El id del recurso cambia cuando ANCAP republica**
# (el 12/10/26 pasó de 019414ce a e3699b01 y la URL vieja dio 404): `descargar()` pregunta al catálogo.
URL_CSV = (
    "https://catalogodatos.gub.uy/dataset/94f39174-333a-46bc-a675-78f20a5a6407/resource/"
    "e3699b01-8649-4d10-a47e-2f951f5c2c8f/download/datos-de-cantidad-de-ventas-de-combustibles.csv"
)
NOMBRE_CSV = "datos-de-cantidad-de-ventas-de-combustibles.csv"

COLUMNAS_ESPERADAS = [
    "Mercado",
    "Mes",
    "Anio",
    "FamiliaDeProducto",
    "LineaDeProducto",
    "Bandera",
    "CantidadCorregida",
    "Unidad",
]
UNIDADES_MEDIDAS = ("Miles de m3", "Toneladas")
UNIDAD_POR_DEFECTO = "Miles de m3"


class AncapVentasInvalido(ValueError):
    """La serie no cumple el contrato de la fuente."""


def _limpiar_encabezado(campos: list[str]) -> list[str]:
    return [c.replace("\ufeff", "").strip() for c in campos]


def leer(ruta: Path) -> list[dict]:
    """Lee el archivo y devuelve una fila por registro, sin agrupar.

    Cada fila es `mercado`, `anio`, `mes`, `familia`, `linea`, `bandera`, `cantidad` (float, o
    `None` si viene vacía) y `unidad`. Los negativos se leen: son correcciones de la fuente.

    Rechaza lo que rompería una suma en silencio: columnas distintas, una fila con otro número de
    campos, un mes que no existe y un número que no se puede leer. **No** rechaza un mercado, una
    familia, una línea ni una bandera nueva —son vocabularios abiertos— ni una unidad nueva, que se
    suma en su propio renglón.
    """
    ruta = Path(ruta)
    if not ruta.is_file():
        raise AncapVentasInvalido(f"{ruta}: el archivo no está en el disco")
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        lector = csv.reader(f, delimiter=";")
        try:
            encabezado = _limpiar_encabezado(next(lector))
        except StopIteration:
            raise AncapVentasInvalido(f"{ruta}: archivo vacío") from None
        if encabezado != COLUMNAS_ESPERADAS:
            raise AncapVentasInvalido(f"{ruta}: columnas inesperadas {encabezado}, se esperaban {COLUMNAS_ESPERADAS}")
        registros = []
        for n, campos in enumerate(lector, start=2):
            if not any(c.strip() for c in campos):
                continue
            if len(campos) != len(COLUMNAS_ESPERADAS):
                raise AncapVentasInvalido(f"{ruta} fila {n}: {len(campos)} columnas")
            mercado, mes_crudo, anio_crudo, familia, linea, bandera, cantidad_cruda, unidad = (
                c.strip() for c in campos
            )
            try:
                anio, mes = int(anio_crudo), int(mes_crudo)
            except ValueError:
                raise AncapVentasInvalido(f"{ruta} fila {n}: año/mes ilegible {campos[1:3]!r}") from None
            if not 1 <= mes <= 12:
                raise AncapVentasInvalido(f"{ruta} fila {n}: mes fuera de 1 a 12: {mes_crudo!r}")
            if not cantidad_cruda:
                cantidad = None
            else:
                cantidad = numero_europeo(cantidad_cruda)
                if cantidad is None:
                    raise AncapVentasInvalido(f"{ruta} fila {n}: cantidad ilegible {cantidad_cruda!r}")
            if not unidad:
                raise AncapVentasInvalido(f"{ruta} fila {n}: la cantidad no dice en qué unidad viene")
            registros.append(
                {
                    "mercado": mercado,
                    "anio": anio,
                    "mes": mes,
                    "familia": familia,
                    "linea": linea,
                    "bandera": bandera,
                    "cantidad": cantidad,
                    "unidad": unidad,
                }
            )
    if not registros:
        raise AncapVentasInvalido(f"{ruta}: archivo sin filas de datos")
    return registros


def serie_mensual(
    registros: list[dict],
    unidad: str = UNIDAD_POR_DEFECTO,
    mercado: Optional[str] = None,
    linea: Optional[str] = None,
) -> list[dict]:
    """Una fila por mes, sumando las banderas. **Pide la unidad a propósito.**

    `Miles de m3` y `Toneladas` no se suman entre sí; y dentro de una unidad, sumar `B/E` con `B/N`
    mezcla banderas distintas, que es lo que se quiere para el total del mercado. Devuelve, por mes
    y en orden, `anio`, `mes`, `cantidad` (float) y `filas`.
    """
    total: dict[tuple[int, int], float] = defaultdict(float)
    cuenta: dict[tuple[int, int], int] = defaultdict(int)
    for r in registros:
        if r["unidad"] != unidad:
            continue
        if mercado is not None and r["mercado"] != mercado:
            continue
        if linea is not None and r["linea"] != linea:
            continue
        if r["cantidad"] is None:
            continue
        total[(r["anio"], r["mes"])] += r["cantidad"]
        cuenta[(r["anio"], r["mes"])] += 1
    return [
        {"anio": anio, "mes": mes, "cantidad": total[(anio, mes)], "filas": cuenta[(anio, mes)]}
        for anio, mes in sorted(total)
    ]


def _faltantes(meses: set[int]) -> list[int]:
    return [m for m in range(1, 13) if m not in meses]


def resumen(registros: list[dict]) -> dict:
    """Totales por unidad y por mercado, la cobertura de meses, y los nulos.

    **La cobertura se declara porque el archivo es una ventana móvil**: si falta un mes, no está en
    cero, no está y punto. `faltan` lista los meses que no vinieron, año por año.
    """
    por_unidad: dict[str, float] = defaultdict(float)
    por_mercado: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    meses_por_anio: dict[int, set[int]] = defaultdict(set)
    nulos = 0
    negativas = 0
    for r in registros:
        meses_por_anio[r["anio"]].add(r["mes"])
        if r["cantidad"] is None:
            nulos += 1
            continue
        if r["cantidad"] < 0:
            negativas += 1
        por_unidad[r["unidad"]] += r["cantidad"]
        por_mercado[r["mercado"]][r["unidad"]] += r["cantidad"]
    return {
        "filas": len(registros),
        "nulos": nulos,
        "correcciones_negativas": negativas,
        "unidades": dict(por_unidad),
        "por_mercado": {m: dict(u) for m, u in por_mercado.items()},
        "cobertura": {
            anio: {"meses": len(meses_por_anio[anio]), "faltan": _faltantes(meses_por_anio[anio])}
            for anio in sorted(meses_por_anio)
        },
    }


def url_vigente() -> str:
    """La URL del CSV de datos que el catálogo publica hoy. **Sale a la red.**

    Se elige por el nombre del archivo: el dataset publica lo mismo en CSV, JSON y XML. Cero o dos
    CSV es un cambio que hay que ver, no adivinar. Si el catálogo no responde se usa `URL_CSV`.
    """
    from uydatos.catalogo import recursos

    try:
        todos = recursos(DATASET)
    except OSError:
        return URL_CSV
    candidatos = [r["url"] for r in todos if r["url"].split("?")[0].rsplit("/", 1)[-1] == NOMBRE_CSV]
    if len(candidatos) != 1:
        raise AncapVentasInvalido(f"{DATASET}: {len(candidatos)} recursos llamados {NOMBRE_CSV}, se esperaba 1")
    return candidatos[0]


def descargar(destino: Path, url: Optional[str] = None) -> Path:
    """Baja el CSV del catálogo a `destino`. **Sale a la red.**

    Sin `url`, la vigente según el catálogo: el id del recurso cambia cuando ANCAP republica.
    """
    return red.bajar(url or url_vigente(), destino)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m uydatos.ancap_ventas", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="orden", required=True)
    b = sub.add_parser("bajar")
    b.add_argument("archivo", type=Path)
    r = sub.add_parser("resumen")
    r.add_argument("archivo", type=Path)
    s = sub.add_parser("serie", help="cantidad por mes de un mercado (y opcionalmente una línea)")
    s.add_argument("archivo", type=Path)
    s.add_argument("mercado")
    s.add_argument("linea", nargs="?")
    s.add_argument("--unidad", default=UNIDAD_POR_DEFECTO)
    args = ap.parse_args(argv)

    if args.orden == "bajar":
        print(f"bajado {descargar(args.archivo)}")
        return 0

    registros = leer(args.archivo)
    if args.orden == "resumen":
        r_ = resumen(registros)
        print(f"{r_['filas']} filas, {r_['nulos']} sin cantidad, {r_['correcciones_negativas']} correcciones")
        for unidad, total in sorted(r_["unidades"].items()):
            print(f"  {unidad:14s} {total:14,.2f}")
        print("cobertura (meses que no vinieron):")
        for anio, c in r_["cobertura"].items():
            print(f"  {anio}: {c['meses']:2d} meses" + (f", faltan {c['faltan']}" if c["faltan"] else ""))
        print("por mercado:")
        for mercado, unidades in sorted(r_["por_mercado"].items(), key=lambda kv: -sum(kv[1].values())):
            detalle = ", ".join(f"{u} {v:,.1f}" for u, v in sorted(unidades.items()))
            print(f"  {mercado:14s} {detalle}")
        return 0

    serie = serie_mensual(registros, unidad=args.unidad, mercado=args.mercado, linea=args.linea)
    print(f"{args.unidad}: {args.mercado}" + (f" / {args.linea}" if args.linea else ""))
    print("anio;mes;cantidad")
    for s_ in serie:
        print(f"{s_['anio']};{s_['mes']:02d};{s_['cantidad']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
