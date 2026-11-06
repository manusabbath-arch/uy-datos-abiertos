"""Lo común a las APIs de SSD/CNEOS de JPL (`ssd-api.jpl.nasa.gov`): firma, cuenta, números y red.

Medido el 2026-11-06 (hora de Uruguay) sobre CAD 1.5, Sentry 2.0 y Fireball 1.2:

- **Los números llegan como strings** (`"0.00963195025335591"`), salvo excepciones que no avisa
  la documentación: `n_imp` de Sentry es **entero** en los 2.239 registros, y la propia
  documentación lo muestra entre comillas (`"n_imp" : "9"`). El lector acepta las dos formas y
  rechaza cualquier otra cosa.
- **`count` cambia de tipo según el API**: entero en CAD (`52247`), string en Sentry (`"2239"`)
  y en Fireball (`"1074"`). Sumar cuentas de dos APIs sin convertir concatena o rompe.
- **La versión viene en `signature.version`** y la documentación pide revisarla. La regla de acá:
  se rechaza si cambia la versión **mayor**; una menor distinta se acepta porque el contrato
  real es la lista de campos, que se valida aparte y entera. Rechazar por cualquier versión
  convierte un campo agregado en una caída.
- **Un error puede venir con HTTP 200**: Sentry responde 200 con `"error": "specified object
  removed"` a un objeto retirado (Apophis, retirado el 2021-02-21 08:22:28). Un lector que mire
  sólo el código HTTP lo lee como un objeto sin datos.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from uydatos import red
from uydatos.errores import DatosInvalidos

from espaciodatos import USER_AGENT

BASE = "https://ssd-api.jpl.nasa.gov"


class JplInvalido(DatosInvalidos):
    """La respuesta de un API de JPL no cumple el contrato medido."""


def ahora_utc() -> datetime:
    """El instante actual en UTC, sin zona: como vienen las fechas de los APIs."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def pedir(url: str) -> bytes:
    """Sale a la red por `uydatos.red`, con el `User-Agent` de este paquete."""
    return red.pedir(url, cabeceras={"User-Agent": USER_AGENT})


def cargar(ruta: Path) -> dict[str, Any]:
    """El JSON de un archivo bajado. Un archivo vacío o que no es JSON se rechaza con el motivo."""
    p = Path(ruta)
    if not p.is_file():
        raise JplInvalido(f"{p}: el archivo no está en el disco")
    texto = p.read_text(encoding="utf-8")
    if not texto.strip():
        raise JplInvalido(f"{p.name}: el archivo está vacío")
    try:
        d = json.loads(texto)
    except json.JSONDecodeError as e:
        raise JplInvalido(f"{p.name}: no es JSON ({e.msg}, línea {e.lineno})") from None
    if not isinstance(d, dict):
        raise JplInvalido(f"{p.name}: se esperaba un objeto JSON y vino {type(d).__name__}")
    return d


def firma(d: dict[str, Any], fuente: str, version: str, nombre: str) -> str:
    """Valida `signature`: la fuente exacta y la misma versión mayor. Devuelve la versión leída."""
    s = d.get("signature")
    if not isinstance(s, dict):
        raise JplInvalido(f"{nombre}: no trae `signature`; todas las respuestas medidas la traen")
    if s.get("source") != fuente:
        raise JplInvalido(f"{nombre}: signature.source {s.get('source')!r}; se esperaba {fuente!r}")
    leida = str(s.get("version", ""))
    if leida.split(".")[0] != version.split(".")[0]:
        raise JplInvalido(
            f"{nombre}: el API está en la versión {leida!r} y el lector se midió con la {version}; "
            "cambió la versión mayor y el formato no está garantizado (lo dice la documentación de JPL)"
        )
    return leida


def cuenta(d: dict[str, Any], datos: list, nombre: str) -> int:
    """`count`, sea entero o string, y que coincida con las filas que vinieron."""
    c = d.get("count")
    if isinstance(c, bool) or not isinstance(c, (int, str)):
        raise JplInvalido(f"{nombre}: count {c!r} no es entero ni string numérico")
    try:
        n = int(c)
    except ValueError:
        raise JplInvalido(f"{nombre}: count {c!r} no es un número") from None
    if n != len(datos):
        raise JplInvalido(
            f"{nombre}: count dice {n} y vinieron {len(datos)} filas; la respuesta está cortada o paginada"
        )
    return n


def numero(v: Any, campo: str, donde: str, *, nulo: bool = False) -> Optional[float]:
    """Un número que el API manda como string. `None` sólo si el campo puede ser nulo."""
    if v is None:
        if nulo:
            return None
        raise JplInvalido(f"{donde}: {campo} es nulo y en lo medido nunca lo es")
    if isinstance(v, bool) or not isinstance(v, (str, int, float)):
        raise JplInvalido(f"{donde}: {campo} {v!r} no es un número")
    try:
        return float(v)
    except ValueError:
        raise JplInvalido(f"{donde}: {campo} ilegible {v!r}; se esperaba un número") from None


def entero(v: Any, campo: str, donde: str) -> int:
    """Un entero que el API manda como int o como string (Sentry `n_imp`: la doc dice string,
    el API manda int)."""
    if isinstance(v, bool):
        raise JplInvalido(f"{donde}: {campo} {v!r} no es un entero")
    if isinstance(v, int):
        return v
    if isinstance(v, str) and v.strip().isdigit():
        return int(v)
    raise JplInvalido(f"{donde}: {campo} {v!r} no es un entero")


def campos(d: dict[str, Any], esperados: list[str], nombre: str) -> list[list]:
    """Valida `fields` contra la lista medida, **entera y en orden**, y devuelve `data`."""
    f = d.get("fields")
    if f != esperados:
        raise JplInvalido(f"{nombre}: fields {f!r}; el contrato medido es {esperados!r}: cambió el formato del API")
    datos = d.get("data", [])
    if not isinstance(datos, list):
        raise JplInvalido(f"{nombre}: data no es una lista")
    for i, fila in enumerate(datos):
        if not isinstance(fila, list) or len(fila) != len(esperados):
            raise JplInvalido(f"{nombre} fila {i}: se esperaban {len(esperados)} valores y vino {fila!r}")
    return datos
