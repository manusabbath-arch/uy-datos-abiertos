"""Sanciones a empresas de Defensa del Consumidor (catálogo de datos abiertos, CKAN).

Dataset `defensa-del-consumidor-sanciones-a-empresas`. Medido el 2026-10-17 sobre el archivo que
publica el catálogo: 168.759 bytes, sha256
`241a78a15e951bf960f93efc12aebe0d04dc343b24198a2fa4899d1872dd4cd0`, **1.528 resoluciones** de 2017
a 2024 (el corte es 2024: el archivo no se actualiza desde entonces, aunque el catálogo declare
`metadata_modified` del 2026-03-22 — el mismo sha256 que el 09/10, o sea que la fecha se movió sin
que el dato cambiara).

**Medido otra vez el 2026-11-27 (issue #13)**: el catálogo publica ahora `datos_sanciones_2017_2025.csv`,
191.915 bytes, sha256 `2389481356510dbfa2115bf33312e286349eeae4527500fdcc2e25b6a066eb26`, **1.835
resoluciones** de 2017 a 2025. Trae cuatro trampas nuevas, todas declaradas en vez de arregladas:

- **La columna del motivo se llama `tipo_infraccion`** (antes `motivo_sancion`), con los mismos
  valores. Se aceptan los dos encabezados; la salida sigue siendo `motivo`.
- **1.738 de 1.835 RUT vienen en notación científica** (`2,17795E+11`): el archivo pasó por Excel y
  perdió dígitos. No se reconstruyen: `rut` es `None`, `rut_crudo` conserva el texto y `resumen()`
  los cuenta en `rut_cientifico`. Solo 97 filas traen un RUT utilizable.
- **Los 229 apercibimientos de 2025 traen el monto vacío** (antes de 2025 venían con 0): `monto_ur`
  es `None`, no 0, y `resumen()` lo cuenta en `monto_sin_dato`.
- **Las 307 resoluciones de 2025 no traen departamento** (texto vacío, devuelto tal cual).

Las trampas medidas el 2026-10-17 (siguen valiendo):

- **El nombre del recurso no es el nombre del archivo.** El recurso se llama «Sanciones aplicadas a
  empresas» y el archivo `datos_sanciones_2017_2024.csv`: buscarlo por el nombre del archivo (lo
  que hace `ancap.url_vigente()`) devuelve 0. Se elige el **único CSV** del dataset.
- **cp1252, no UTF-8**, con `;` de delimitador: leerlo como UTF-8 convierte la «ñ» en basura y no
  falla.
- **El `rut` viene con relleno de espacios a la derecha** (1.443 de 1.528 filas): sin `.strip()` la
  clave del cruce no coincide con nada.
- **Una fila trae un `rut` de 3 caracteres** (un vacío mal exportado). No se descarta en silencio:
  se devuelve tal cual, y `resumen()` cuenta cuántos RUT no tienen 12 caracteres.
- **La fecha es d/m/AAAA de ancho variable** (`31/5/2018`, `20/7/2018`): se parsea con una expresión
  regular, no con `strptime`.
- **`monto_ur` = 0 es un cero medido** (un apercibimiento no tiene multa), no un dato faltante: los
  831 apercibimientos vienen con 0. No hay ningún monto vacío en las 1.528 filas.
- **Sólo aparecen 13 de los 19 departamentos, y Salto no está entre ellos** (Montevideo 1.257 y
  Canelones 115): si aparece una resolución salteña, la fuente cambió.
- **El archivo trae `razon_social` y `rut` de terceros.** Es un dato público —está en el catálogo
  abierto— y el lector devuelve las filas **tal cual**: qué se versiona y qué se cruza no es
  decisión de esta función. El límite está escrito en el README (`## Datos personales`).

Uso:
    python -m uydatos.sanciones bajar datos/sanciones.csv
    python -m uydatos.sanciones resumen datos/sanciones.csv
    python -m uydatos.sanciones filas datos/sanciones.csv --limite 20
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Optional, Sequence

from uydatos import catalogo, red
from uydatos.errores import DatosInvalidos

DATASET = "defensa-del-consumidor-sanciones-a-empresas"
COLUMNAS = [
    "razon_social",
    "nombre_comercial",
    "rut",
    "departamento",
    "fecha_resolucion",
    "motivo_sancion",
    "tipo_sancion",
    "monto_ur",
]
# El 2026-11 el archivo pasó a llamar `tipo_infraccion` a la columna del motivo (mismos valores).
COLUMNAS_2025 = [c if c != "motivo_sancion" else "tipo_infraccion" for c in COLUMNAS]
CODIFICACION = "cp1252"
_RUT_CIENTIFICO = re.compile(r"^\d+(?:[.,]\d+)?E\+\d+$", re.IGNORECASE)
DELIMITADOR = ";"


class SancionesInvalido(DatosInvalidos):
    """El archivo no cumple el contrato de la fuente."""


def url_vigente() -> str:
    """La URL del único CSV del dataset. **Sale a la red.** Cero o dos CSV se rechazan."""
    recursos = catalogo.recursos(DATASET)
    csv = [r for r in recursos if r["formato"] == "CSV"]
    if len(csv) != 1:
        raise SancionesInvalido(f"{DATASET}: {len(csv)} recursos CSV, se esperaba 1: {[r['nombre'] for r in csv]}")
    return csv[0]["url"]


def descargar(destino: Path, url: Optional[str] = None) -> Path:
    """Baja el CSV a `destino`. **Sale a la red.** Con `url` explícita no consulta el catálogo."""
    return red.bajar(url or url_vigente(), destino)


_FECHA = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")


def _fecha(texto: str, ruta: Path, fila: int) -> date:
    m = _FECHA.match(texto.strip())
    if not m:
        raise SancionesInvalido(f"{ruta.name} fila {fila}: fecha ilegible {texto!r}, se esperaba d/m/AAAA")
    dia, mes, anio = (int(g) for g in m.groups())
    try:
        return date(anio, mes, dia)
    except ValueError as e:
        raise SancionesInvalido(f"{ruta.name} fila {fila}: fecha imposible {texto!r} ({e})") from e


def leer(ruta: Path) -> list[dict]:
    """Las resoluciones, una por fila, con `rut` sin relleno y `fecha` como `date`.

    `monto_ur` es `int` (0 es un cero medido). Las columnas de texto se devuelven tal cual vienen,
    sin normalizar mayúsculas ni tildes: quien cruce decide eso.
    """
    ruta = Path(ruta)
    if not ruta.is_file():
        raise SancionesInvalido(f"{ruta}: el archivo no está en el disco")
    with ruta.open(encoding=CODIFICACION, newline="") as f:
        lector = csv.reader(f, delimiter=DELIMITADOR)
        try:
            encabezado = [c.replace("\ufeff", "").strip() for c in next(lector)]
        except StopIteration:
            raise SancionesInvalido(f"{ruta}: archivo vacío") from None
        if encabezado not in (COLUMNAS, COLUMNAS_2025):
            raise SancionesInvalido(f"{ruta}: columnas inesperadas {encabezado}, se esperaban {COLUMNAS}")
        filas = []
        for n, campos in enumerate(lector, start=2):
            if not any(c.strip() for c in campos):
                continue
            if len(campos) != len(COLUMNAS):
                raise SancionesInvalido(f"{ruta} fila {n}: {len(campos)} columnas, se esperaban {len(COLUMNAS)}")
            razon, comercial, rut, dpto, fecha_cruda, motivo, tipo, monto_crudo = (c.strip() for c in campos)
            try:
                monto: Optional[int] = int(monto_crudo) if monto_crudo else None  # vacío = sin dato, no 0
            except ValueError:
                raise SancionesInvalido(f"{ruta} fila {n}: monto ilegible {monto_crudo!r} (no es un entero)") from None
            filas.append(
                {
                    "razon_social": razon,
                    "nombre_comercial": comercial,
                    # `2,17795E+11`: Excel ya perdió dígitos. Convertirlo daría un RUT inventado.
                    "rut": None if _RUT_CIENTIFICO.match(rut) else rut,
                    "rut_crudo": rut,
                    "departamento": dpto,
                    "fecha": _fecha(fecha_cruda, ruta, n),
                    "motivo": motivo,
                    "tipo": tipo,
                    "monto_ur": monto,
                }
            )
    if not filas:
        raise SancionesInvalido(f"{ruta}: archivo sin filas de datos")
    return filas


def resumen(filas: list[dict]) -> dict:
    """Las cuentas que el documento del 09/10 ya declara: cuántas, por motivo, por tipo, y qué
    se declara en vez de corregirse (RUT que no tienen 12 caracteres, años, departamentos)."""
    if not filas:
        raise SancionesInvalido("resumen() necesita al menos una fila: el archivo vino vacío")
    return {
        "filas": len(filas),
        "por_motivo": dict(Counter(f["motivo"] for f in filas).most_common()),
        "por_tipo": dict(Counter(f["tipo"] for f in filas).most_common()),
        "rut_sin_12": sum(1 for f in filas if f["rut"] is not None and len(f["rut"]) != 12),
        "rut_cientifico": sum(1 for f in filas if f["rut"] is None),
        "monto_sin_dato": sum(1 for f in filas if f["monto_ur"] is None),
        "anio_min": min(f["fecha"].year for f in filas),
        "anio_max": max(f["fecha"].year for f in filas),
        "departamentos": dict(Counter(f["departamento"] for f in filas).most_common()),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m uydatos.sanciones", description=__doc__.splitlines()[0])
    ap.add_argument("accion", choices=["bajar", "resumen", "filas"])
    ap.add_argument("ruta", type=Path)
    ap.add_argument("--limite", type=int, default=10)
    args = ap.parse_args(argv)
    if args.accion == "bajar":
        print(descargar(args.ruta))
        return 0
    filas = leer(args.ruta)
    if args.accion == "filas":
        for f in filas[: args.limite]:
            print(f"{f['fecha']} {f['departamento']:<12} {f['tipo']:<15} {f['motivo']:<28} {f['razon_social'][:40]}")
        return 0
    r = resumen(filas)
    print(
        f"{r['filas']} resoluciones de {r['anio_min']} a {r['anio_max']} · RUT sin 12: {r['rut_sin_12']}"
        f" · RUT en notación científica (irrecuperables): {r['rut_cientifico']} · monto sin dato: {r['monto_sin_dato']}"
    )
    for k, v in list(r["por_motivo"].items())[:5]:
        print(f"  {v:>4}  {k}")
    print("  por departamento:", ", ".join(f"{k} {v}" for k, v in list(r["departamentos"].items())[:5]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
