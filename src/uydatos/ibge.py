"""IPCA de Brasil (IBGE), número-índice, desde la API SIDRA (tabla 1737, variable 2266).

Base diciembre 1993 = 100. Sin clave.

Las trampas, y por qué el lector las corta
-----------------------------------------
1. **La tabla 1737 trae varias variables** (variación mensual 63, acumulada en 12 meses 2265,
   número-índice 2266...). Una variación leída como índice no da error. Se exige 2266 y la
   unidad `Número-índice`.
2. **El dato faltante es `...` o `-`**: un nulo, no un cero.
3. **La primera fila es el diccionario de columnas**, no un dato.
4. Un **índice no es una inflación**: el lector devuelve el índice.

Uso:
    python -m uydatos.ibge bajar ipca.json
    python -m uydatos.ibge leer ipca.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

from uydatos import USER_AGENT

URL = "https://apisidra.ibge.gov.br/values/t/1737/n1/all/v/2266/p/all"
VARIABLE = "2266"
UNIDAD = "Número-índice"
SIN_DATO = ("...", "-", "..", "X", "")


class IpcaInvalido(ValueError):
    """La respuesta de SIDRA no cumple el contrato de la fuente."""


def leer(ruta: Path) -> list[dict]:
    """[{periodo: 'AAAA-MM', valor: float}] del número-índice. Rechaza en vez de arreglar."""
    ruta = Path(ruta)
    try:
        filas = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise IpcaInvalido(f"{ruta}: ilegible ({e})") from None
    if not isinstance(filas, list) or len(filas) < 2:
        raise IpcaInvalido(f"{ruta}: sin filas de datos (la primera es el diccionario de columnas)")
    serie = []
    for f in filas[1:]:
        if f.get("D2C") != VARIABLE or f.get("MN") != UNIDAD:
            raise IpcaInvalido(
                f"{ruta}: fila de la variable {f.get('D2C')} ({f.get('MN')}); se exige {VARIABLE} ({UNIDAD})"
            )
        valor = (f.get("V") or "").strip()
        if valor in SIN_DATO:
            continue
        p = f["D3C"]
        serie.append({"periodo": f"{p[:4]}-{p[4:6]}", "valor": float(valor)})
    if not serie:
        raise IpcaInvalido(f"{ruta}: ninguna fila con valor")
    return serie


def _pedido():
    import urllib.request

    return urllib.request.Request(URL, headers={"User-Agent": USER_AGENT})


def descargar(destino: Path) -> Path:
    """Baja la serie completa a `destino`. **Única función que sale a la red.**"""
    import urllib.request

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(_pedido(), timeout=90) as r:  # noqa: S310 — host fijo
        destino.write_bytes(r.read())
    return destino


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m uydatos.ibge", description=__doc__.splitlines()[0])
    ap.add_argument("orden", choices=["bajar", "leer"])
    ap.add_argument("archivo", type=Path)
    args = ap.parse_args(argv)
    if args.orden == "bajar":
        print(f"bajado {descargar(args.archivo)}")
        return 0
    serie = leer(args.archivo)
    print(f"IPCA número-índice: {len(serie)} meses, {serie[0]['periodo']} a {serie[-1]['periodo']}")
    for s in serie[-3:]:
        print(f"  {s['periodo']}: {s['valor']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
