"""Recursos del catálogo de datos abiertos de Uruguay (catalogodatos.gub.uy, CKAN).

Las URLs de descarga de un dataset cambian cuando el organismo vuelve a subir un archivo. En vez
de fijarlas, se le pregunta al catálogo con `package_show` cuáles son las vigentes.

Uso:
    python -m uydatos.catalogo inia-precipitacion-temps-extremas-sg
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

API = "https://catalogodatos.gub.uy/api/3/action/package_show"


class CatalogoInvalido(ValueError):
    """La respuesta del catálogo no cumple el contrato de CKAN."""


def parsear_package_show(crudo: dict) -> list[dict]:
    """De una respuesta de `package_show`, la lista de recursos con `nombre`, `url`, `formato`
    y `modificado`. Rechaza una respuesta con `success` falso o sin recursos."""
    if not crudo.get("success"):
        raise CatalogoInvalido(f"el catálogo respondió success={crudo.get('success')!r}: {crudo.get('error')}")
    recursos = (crudo.get("result") or {}).get("resources") or []
    if not recursos:
        raise CatalogoInvalido("el dataset no tiene recursos")
    return [
        {
            "nombre": r.get("name") or "",
            "url": r.get("url") or "",
            "formato": (r.get("format") or "").upper(),
            "modificado": r.get("last_modified") or r.get("metadata_modified") or "",
        }
        for r in recursos
    ]


def recursos(dataset: str) -> list[dict]:
    """Los recursos vigentes de un dataset. **Sale a la red.**"""
    import urllib.parse
    import urllib.request

    from uydatos import USER_AGENT

    url = f"{API}?{urllib.parse.urlencode({'id': dataset})}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 — host fijo
        return parsear_package_show(json.loads(r.read().decode("utf-8")))


def bajar_recurso(url: str, destino: Path) -> Path:
    """Baja un recurso a `destino`. **Sale a la red.**"""
    import urllib.request

    from uydatos import USER_AGENT

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=90) as r:  # noqa: S310 — URL del catálogo
        destino.write_bytes(r.read())
    return destino


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m uydatos.catalogo", description=__doc__.splitlines()[0])
    ap.add_argument("dataset")
    args = ap.parse_args(argv)
    for r in recursos(args.dataset):
        print(f"{r['formato']:5} {r['modificado'][:10]}  {r['nombre']}\n      {r['url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
