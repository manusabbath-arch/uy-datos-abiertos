"""El sello que cierra un informe: de donde salio el numero y de cuando es.

Hoy la trazabilidad esta repartida: `fuente` y `bajado` escritos a mano en cada herramienta del
servidor MCP, el sha256 a mano en los tests de red, y `cache.sello()` en el propio servidor. Aca
se vuelve una sola cosa: el mismo sello para cualquier informe que use el paquete.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, TypedDict


class Sello(TypedDict):
    """Lo que hay que poder citar de un numero: quien lo publica y de cuando es la copia."""

    fuente: str
    url: Optional[str]
    bajado: Optional[str]
    sha256: Optional[str]
    bytes: Optional[int]
    filas: Optional[int]


def sha256(ruta: Path) -> str:
    """El sha256 de un archivo, de a bloques para no cargar 12 MB en memoria."""
    h = hashlib.sha256()
    with Path(ruta).open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def sello(
    fuente: str,
    *,
    ruta: Optional[Path] = None,
    url: Optional[str] = None,
    filas: Optional[int] = None,
    bajado: Optional[datetime] = None,
) -> Sello:
    """Arma el sello. Con `ruta`, el sha256 y la fecha salen del archivo; `bajado` los puede pisar.

    Una `ruta` que no existe se rechaza: un sello sin sha256 de un archivo que se dijo tener no es un
    sello, es una cita sin respaldo."""
    if ruta is not None:
        p = Path(ruta)
        if not p.is_file():
            raise FileNotFoundError(f"{p}: no se puede sellar un archivo que no está")
        bajado = bajado or datetime.fromtimestamp(p.stat().st_mtime)
        return {
            "fuente": fuente,
            "url": url,
            "bajado": bajado.isoformat(timespec="minutes"),
            "sha256": sha256(p),
            "bytes": p.stat().st_size,
            "filas": filas,
        }
    return {
        "fuente": fuente,
        "url": url,
        "bajado": bajado.isoformat(timespec="minutes") if bajado else None,
        "sha256": None,
        "bytes": None,
        "filas": filas,
    }


def como_linea(s: Sello) -> str:
    """El sello en una linea, para el pie de un informe."""
    partes = [s["fuente"]]
    if s["bajado"]:
        partes.append(f"bajado {s['bajado'].replace('T', ' ')}")
    if s["filas"] is not None:
        partes.append(f"{s['filas']:,} filas".replace(",", "."))
    if s["sha256"]:
        partes.append(f"sha256:{s['sha256'][:12]}")
    if s["bytes"] is not None:
        partes.append(f"{s['bytes']:,} bytes".replace(",", "."))
    if s["url"]:
        partes.append(s["url"])
    return " · ".join(partes)
