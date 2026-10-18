"""Comparar dos copias de la misma fuente: qué cambió, y si el cambio es de dominio.

`procedencia.sello()` dice de dónde salió un número; esto contesta la otra mitad. Medido el
2026-10-17: el archivo de sanciones del DSS declara `metadata_modified` del 2026-03-22 y su sha256
es el mismo del 2026-10-09 — la fecha se movió sin que el archivo cambiara. Al revés también pasa:
ANCAP republicó el 2026-10-12 y cambió el id del recurso. Un sello sin comparación dice «algo».

La regla es la de `docs/plantilla-lector.md`: **un cambio de columnas no es una revisión, es otra
fuente**, y se rechaza. Una fila con una clave repetida tampoco se compara: no se puede decir cuál
de las dos cambió.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Sequence


class RevisionInvalida(ValueError):
    """Las dos copias no se pueden comparar con la clave pedida."""


def _leer(ruta: Path, delimitador: str, codificacion: str) -> tuple[list[str], list[list[str]]]:
    ruta = Path(ruta)
    if not ruta.is_file():
        raise RevisionInvalida(f"{ruta}: no está en el disco")
    try:
        with ruta.open(encoding=codificacion, newline="") as f:
            lector = csv.reader(f, delimiter=delimitador)
            try:
                encabezado = [c.replace("\ufeff", "").strip() for c in next(lector)]
            except StopIteration:
                raise RevisionInvalida(f"{ruta}: archivo vacío") from None
            filas = [campos for campos in lector if any(c.strip() for c in campos)]
    except UnicodeDecodeError as e:
        # La codificación se pide explícita porque no se adivina el dialecto: si no coincide, el
        # rechazo dice qué archivo es y con qué se intentó, en vez de dejar escapar el codec.
        raise RevisionInvalida(f"{ruta}: no se puede leer como {codificacion} ({e})") from None
    return encabezado, filas


def comparar(
    antes: Path,
    despues: Path,
    *,
    clave: Sequence[str],
    delimitador: str = ";",
    codificacion: str = "utf-8",
    muestra: int = 20,
) -> dict:
    """Compara dos copias por `clave` y declara qué cambió.

    `delimitador` y `codificacion` se piden explícitos: la mayoría de los archivos del catálogo
    viene con `;`, y el de sanciones con cp1252 (medido). Adivinar el dialecto es exactamente lo
    que este paquete no hace, y si la codificación no coincide el rechazo nombra el archivo que no
    se pudo leer.
    """
    enc_a, filas_a = _leer(antes, delimitador, codificacion)
    enc_d, filas_d = _leer(despues, delimitador, codificacion)
    if enc_a != enc_d:
        agregadas = [c for c in enc_d if c not in enc_a]
        quitadas = [c for c in enc_a if c not in enc_d]
        if not agregadas and not quitadas:
            # Mismo juego de columnas en otro orden: el motivo lo dice, porque la comparación es
            # por posición y el mismo dato en otra columna es otro dato.
            raise RevisionInvalida(
                f"columnas distintas: las mismas en otro orden ({enc_a} → {enc_d}). "
                "Un cambio de columnas es otra fuente."
            )
        raise RevisionInvalida(
            f"columnas distintas: agregadas {agregadas}, quitadas {quitadas}. Un cambio de columnas es otra fuente."
        )
    for nombre, enc, filas, ruta in (("antes", enc_a, filas_a, antes), ("después", enc_d, filas_d, despues)):
        for n, campos in enumerate(filas, start=2):
            if len(campos) != len(enc):
                raise RevisionInvalida(f"{ruta} ({nombre}) fila {n}: {len(campos)} columnas, se esperaban {len(enc)}")
    indices = [enc_a.index(c) for c in clave] if all(c in enc_a for c in clave) else None
    if indices is None:
        raise RevisionInvalida(f"la clave {list(clave)} no está en las columnas {enc_a}")

    def tabla(filas: list[list[str]], ruta: Path) -> dict[tuple, list[str]]:
        salida: dict[tuple, list[str]] = {}
        for n, campos in enumerate(filas, start=2):
            k = tuple(campos[i].strip() for i in indices)
            if any(not v for v in k):
                continue  # una fila sin clave no es una fila de dato: se saltea y se cuenta aparte
            if k in salida:
                raise RevisionInvalida(f"{ruta} fila {n}: clave repetida {k}")
            salida[k] = campos
        return salida

    ta, td = tabla(filas_a, antes), tabla(filas_d, despues)
    cambiadas = sorted(k for k in ta.keys() & td.keys() if ta[k] != td[k])
    agregadas = sorted(td.keys() - ta.keys())
    quitadas = sorted(ta.keys() - td.keys())
    sin_clave = (len(filas_a) - len(ta)) + (len(filas_d) - len(td))
    return {
        "columnas": enc_a,
        "cambio": bool(cambiadas or agregadas or quitadas),
        "filas_agregadas": len(agregadas),
        "filas_quitadas": len(quitadas),
        "filas_cambiadas": len(cambiadas),
        "claves_cambiadas": [list(k) for k in cambiadas[:muestra]],
        "claves_agregadas": [list(k) for k in agregadas[:muestra]],
        "claves_quitadas": [list(k) for k in quitadas[:muestra]],
        "sin_clave": sin_clave,
    }
