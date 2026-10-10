"""Parlamento del Uruguay: asistencias de las dos cámaras, proyectos entrados y leyes promulgadas.

El catálogo publica un archivo por legislatura: asistencias del Senado y de Diputados de la 46 (2005)
a la 50 (la actual), proyectos entrados de la 42 (1985) a la 50, y un único archivo de leyes
promulgadas desde 1985. La medición completa está en `docs/2026-10-10-datos-civicos.md`.

Las trampas, medidas el 10/10/2026
---------------------------------
1. **Todos los recursos de un dataset tienen la misma URL final, `csv`.** Quien los guarda por el
   nombre de la URL pisa una legislatura con otra. La legislatura sale del **título** del recurso.
2. **Hay muchas más personas que bancas**: 336 a 424 filas por legislatura en Diputados (99 bancas),
   ~110 en el Senado (31). Son los suplentes, con una o dos citaciones. Un ranking sin un mínimo de
   citaciones compara a quien fue citado 2 veces con quien fue citado 364.
3. **No hay identificador de persona**: dos filas con el mismo nombre en una legislatura (de 1 a 3 por
   legislatura) pueden ser dos períodos de la misma persona o dos personas. No se unen.
4. **Filas sin nombre** (`","`) con citaciones, en Diputados 49 y 50.
5. **Una columna trae un tabulador pegado** (`'Faltas c/Aviso\\t'`).
6. Lo que sí cierra siempre, y se exige: **citaciones = asistencias + faltas con aviso + faltas sin
   aviso**, en las 10 legislaturas. Las licencias no son citaciones: van aparte.
7. **311 proyectos aparecen en dos legislaturas** con el mismo número de asunto: sumar legislaturas
   los cuenta dos veces.
8. **Leyes**: 4.799 filas son 4.796 leyes (de la 15.736 a la 20.531, sin huecos), más **2 filas
   duplicadas** exactas y una **«ley 0»** (una pensión graciable de 1997). Las columnas
   `Leyes_Referenciadas` y `Leyes_que_referencia` son **cantidades**, no listas. Y el catálogo dice
   que el archivo se actualizó el 21/06/2024 cuando llega a octubre de 2026: la fecha del catálogo no
   dice de cuándo es el dato.

Uso:
    python -m uydatos.parlamento bajar asistencias-senado 50 datos/senado50.csv
    python -m uydatos.parlamento asistencias datos/senado50.csv --minimo 10
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Optional, Sequence

from uydatos import catalogo, red

DATASETS = {
    "asistencias-senado": "parlamento-del-uruguay-asistencias-a-la-camara-de-senadores",
    "asistencias-diputados": "parlamento-del-uruguay-asistencias-a-la-camara-de-representantes",
    "proyectos": "parlamento-del-uruguay-proyectos-entrados-al-parlamento",
    "leyes": "parlamento-del-uruguay-leyes-promulgadas-del-poder-ejecutivo",
}

_COLUMNAS_ASISTENCIA = {
    "nombre": "nombre",
    "citaciones": "citaciones",
    "asistencias": "asistencias",
    "faltasc/aviso": "faltas_con_aviso",
    "cantidaddefaltassinaviso": "faltas_sin_aviso",
    "nocitadoporlicencia": "licencias",
    "pasajesapresidentedelarepublica": "pasajes_a_presidente",
}
_CARPETA = re.compile(r"([A-Z.]+)\s*:\s*(\d+)\s*/\s*(\d{4})")
_TIPO = re.compile(r"\s*\(([^()]*)\)\s*$")


class ParlamentoInvalido(ValueError):
    """El archivo no cumple el contrato del Parlamento."""


def _clave(columna: str) -> str:
    sin = unicodedata.normalize("NFKD", columna).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", "", sin).lower()


def _sin_tildes(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().upper().strip()


def _leer_csv(ruta: Path) -> tuple[list[str], list[list[str]]]:
    ruta = Path(ruta)
    try:
        with ruta.open(encoding="utf-8-sig", newline="") as f:
            filas = list(csv.reader(f))
    except (OSError, UnicodeDecodeError) as e:
        raise ParlamentoInvalido(f"{ruta.name}: ilegible ({e})") from None
    if len(filas) < 2:
        raise ParlamentoInvalido(f"{ruta.name}: sin filas de datos")
    encabezado = filas[0]
    datos = [f for f in filas[1:] if any(c.strip() for c in f)]
    for n, f in enumerate(datos, start=2):
        if len(f) != len(encabezado):
            raise ParlamentoInvalido(f"{ruta.name} fila {n}: {len(f)} campos y el encabezado tiene {len(encabezado)}")
    return encabezado, datos


def _entero(texto: str, donde: str) -> int:
    t = texto.strip()
    if not t:
        return 0
    if not t.isdigit():
        raise ParlamentoInvalido(f"{donde}: {texto!r} no es un entero")
    return int(t)


def legislatura_del_titulo(titulo: str) -> Optional[int]:
    """`Asistencias al Senado - Legislatura 50` -> 50. La URL de todos los recursos termina en `csv`."""
    m = re.search(r"Legislatura\s+(\d+)", titulo or "")
    return int(m.group(1)) if m else None


# --- Asistencias -------------------------------------------------------------------------------------


def leer_asistencias(ruta: Path) -> list[dict]:
    """Una fila por persona y legislatura: nombre (None si viene vacío), citaciones, asistencias, faltas
    con y sin aviso, licencias, pasajes a presidente y `pct_asistencia` calculado. Rechaza una fila donde
    citaciones ≠ asistencias + faltas con aviso + faltas sin aviso."""
    ruta = Path(ruta)
    encabezado, datos = _leer_csv(ruta)
    claves = [_clave(c) for c in encabezado]
    faltan = [c for c in _COLUMNAS_ASISTENCIA if c not in claves]
    if faltan:
        raise ParlamentoInvalido(f"{ruta.name}: faltan columnas {faltan}: no parecen asistencias")
    i = {destino: claves.index(origen) for origen, destino in _COLUMNAS_ASISTENCIA.items()}
    out = []
    for n, fila in enumerate(datos, start=2):
        donde = f"{ruta.name} fila {n}"
        nombre = fila[i["nombre"]].strip()
        f = {"nombre": nombre if nombre.strip(" ,") else None}
        for campo in (
            "citaciones",
            "asistencias",
            "faltas_con_aviso",
            "faltas_sin_aviso",
            "licencias",
            "pasajes_a_presidente",
        ):
            f[campo] = _entero(fila[i[campo]], donde)
        if f["citaciones"] != f["asistencias"] + f["faltas_con_aviso"] + f["faltas_sin_aviso"]:
            raise ParlamentoInvalido(
                f"{donde}: citaciones {f['citaciones']} ≠ asistencias {f['asistencias']} + faltas con aviso "
                f"{f['faltas_con_aviso']} + faltas sin aviso {f['faltas_sin_aviso']}"
            )
        f["pct_asistencia"] = round(100 * f["asistencias"] / f["citaciones"], 1) if f["citaciones"] else None
        out.append(f)
    return out


def resumen_asistencias(filas: list[dict], minimo_citaciones: int = 10, nombre: str = "", cantidad: int = 10) -> dict:
    """La asistencia de una legislatura: menor y mayor asistencia entre quienes tuvieron al menos
    `minimo_citaciones` (los suplentes con una o dos citaciones no dicen nada), los nombres repetidos,
    las filas sin nombre y, con `nombre`, las filas que lo contienen (sin importar tildes)."""
    con_nombre = [f for f in filas if f["nombre"]]
    repetidos = sorted(k for k, v in Counter(f["nombre"] for f in con_nombre).items() if v > 1)
    elegibles = [f for f in con_nombre if f["citaciones"] >= minimo_citaciones]
    orden = sorted(elegibles, key=lambda f: (f["pct_asistencia"], -f["citaciones"]))
    buscado = _sin_tildes(nombre)
    return {
        "personas": len(filas),
        "filas_sin_nombre": len(filas) - len(con_nombre),
        "nombres_repetidos": repetidos,
        "minimo_citaciones": minimo_citaciones,
        "con_el_minimo": len(elegibles),
        "fuera_por_pocas_citaciones": len(con_nombre) - len(elegibles),
        "citaciones_totales": sum(f["citaciones"] for f in filas),
        "menor_asistencia": orden[:cantidad],
        "mayor_asistencia": list(reversed(orden[-cantidad:])) if orden else [],
        "encontrados": [f for f in con_nombre if buscado and buscado in _sin_tildes(f["nombre"])],
    }


# --- Proyectos ---------------------------------------------------------------------------------------


def leer_proyectos(ruta: Path) -> list[dict]:
    """Los proyectos entrados de una legislatura: fecha, asunto (número), carpetas (órgano, número,
    año), título sin el tipo, y tipo («PROYECTO DE LEY», «PROYECTO DE RESOLUCION»…)."""
    ruta = Path(ruta)
    encabezado, datos = _leer_csv(ruta)
    claves = [_clave(c) for c in encabezado]
    if claves[:4] != ["fecha", "asunto", "carpetas", "titulo"]:
        raise ParlamentoInvalido(f"{ruta.name}: columnas {encabezado}: no parecen proyectos entrados")
    out, vistos = [], set()
    for n, (fecha, asunto, carpetas, titulo, *_) in enumerate(datos, start=2):
        donde = f"{ruta.name} fila {n}"
        try:
            dia = date.fromisoformat(fecha.strip())
        except ValueError:
            raise ParlamentoInvalido(f"{donde}: fecha ilegible {fecha!r}") from None
        num = _entero(asunto, donde)
        if num in vistos:
            raise ParlamentoInvalido(f"{donde}: asunto {num} repetido en la misma legislatura")
        vistos.add(num)
        m = _TIPO.search(titulo)
        out.append(
            {
                "fecha": dia,
                "asunto": num,
                "carpetas": [{"organo": o, "numero": int(c), "anio": int(a)} for o, c, a in _CARPETA.findall(carpetas)],
                "titulo": titulo[: m.start()].strip() if m else titulo.strip(),
                "tipo": m.group(1).strip() if m else None,
            }
        )
    return out


# --- Leyes -------------------------------------------------------------------------------------------


def leer_leyes(ruta: Path) -> dict:
    """Las leyes promulgadas, sin duplicados exactos ni registros sin número.

    Devuelve `leyes` (ordenadas por número), `duplicadas` (filas idénticas descartadas), `sin_numero`
    (las filas con número 0) y `faltantes` (los números que no están entre el menor y el mayor). Un
    mismo número con dos contenidos distintos se rechaza: no se sabe cuál es el bueno."""
    ruta = Path(ruta)
    encabezado, datos = _leer_csv(ruta)
    claves = [_clave(c) for c in encabezado]
    req = ("fecha", "numero_de_ley", "texto_original", "texto_actualizado", "titulo", "asunto")
    if any(c not in claves for c in req):
        raise ParlamentoInvalido(f"{ruta.name}: columnas {encabezado}: no parecen leyes promulgadas")
    i = {c: claves.index(c) for c in claves}
    por_numero: dict[int, dict] = {}
    duplicadas, sin_numero = 0, []
    for n, fila in enumerate(datos, start=2):
        donde = f"{ruta.name} fila {n}"
        num = _entero(fila[i["numero_de_ley"]], donde)
        try:
            dia = date.fromisoformat(fila[i["fecha"]].strip())
        except ValueError:
            raise ParlamentoInvalido(f"{donde}: fecha ilegible {fila[i['fecha']]!r}") from None
        ley = {
            "numero": num,
            "fecha": dia,
            "titulo": fila[i["titulo"]].strip(),
            "asunto": fila[i["asunto"]].strip(),
            "texto_parlamento": fila[i["texto_original"]].strip(),
            "texto_impo": fila[i["texto_actualizado"]].strip(),
            "cantidad_que_cita": _entero(fila[i["leyes_referenciadas"]], donde) if "leyes_referenciadas" in i else None,
            "cantidad_que_la_citan": _entero(fila[i["leyes_que_referencia"]], donde)
            if "leyes_que_referencia" in i
            else None,
        }
        if num == 0:
            sin_numero.append(ley)
            continue
        if num in por_numero:
            if por_numero[num] != ley:
                raise ParlamentoInvalido(f"{donde}: la ley {num} aparece dos veces con contenido distinto")
            duplicadas += 1
            continue
        por_numero[num] = ley
    numeros = sorted(por_numero)
    faltantes = sorted(set(range(numeros[0], numeros[-1] + 1)) - set(numeros)) if numeros else []
    return {
        "leyes": [por_numero[k] for k in numeros],
        "duplicadas": duplicadas,
        "sin_numero": sin_numero,
        "faltantes": faltantes,
    }


# --- Descarga ----------------------------------------------------------------------------------------


def recursos_por_legislatura(clave: str) -> dict[int, str]:
    """{legislatura: url} de un dataset por legislatura. **Sale a la red.**"""
    if clave not in DATASETS or clave == "leyes":
        raise ParlamentoInvalido(f"{clave!r}: asistencias-senado, asistencias-diputados o proyectos")
    out: dict[int, str] = {}
    for r in catalogo.recursos(DATASETS[clave]):
        leg = legislatura_del_titulo(r["nombre"])
        if r["formato"] != "CSV" or leg is None:
            continue
        if leg in out:
            raise ParlamentoInvalido(f"{DATASETS[clave]}: dos recursos para la legislatura {leg}")
        out[leg] = r["url"]
    return out


def descargar(clave: str, destino: Path, legislatura: Optional[int] = None) -> Path:
    """Baja un archivo: `leyes`, o `asistencias-senado`, `asistencias-diputados` o `proyectos` de una
    legislatura. **Sale a la red.**"""
    if clave == "leyes":
        csvs = [
            r for r in catalogo.recursos(DATASETS["leyes"]) if r["formato"] == "CSV" and "etadato" not in r["nombre"]
        ]
        if len(csvs) != 1:
            raise ParlamentoInvalido(f"{DATASETS['leyes']}: {len(csvs)} CSV de leyes, se esperaba 1")
        return red.bajar(csvs[0]["url"], Path(destino))
    urls = recursos_por_legislatura(clave)
    if legislatura not in urls:
        raise ParlamentoInvalido(f"{clave}: no hay legislatura {legislatura}; hay {sorted(urls)}")
    return red.bajar(urls[legislatura], Path(destino))


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m uydatos.parlamento", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="orden", required=True)
    b = sub.add_parser("bajar")
    b.add_argument("clave", choices=sorted(DATASETS))
    b.add_argument("legislatura", type=int, nargs="?")
    b.add_argument("destino", type=Path)
    a = sub.add_parser("asistencias")
    a.add_argument("archivo", type=Path)
    a.add_argument("--minimo", type=int, default=10)
    a.add_argument("--nombre", default="")
    args = ap.parse_args(argv)
    if args.orden == "bajar":
        print(f"bajado {descargar(args.clave, args.destino, args.legislatura)}")
        return 0
    r = resumen_asistencias(leer_asistencias(args.archivo), args.minimo, args.nombre)
    print(f"{r['personas']} filas, {r['con_el_minimo']} con al menos {args.minimo} citaciones")
    print(f"sin nombre: {r['filas_sin_nombre']}; nombres repetidos: {r['nombres_repetidos']}")
    for f in r["encontrados"] or r["menor_asistencia"]:
        print(f"  {f['nombre']:35} {f['asistencias']:>4}/{f['citaciones']:<4} {f['pct_asistencia']}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
