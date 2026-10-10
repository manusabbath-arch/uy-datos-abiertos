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

from uydatos import red

API = "https://catalogodatos.gub.uy/api/3/action/package_show"


class CatalogoInvalido(ValueError):
    """La respuesta del catálogo no cumple el contrato de CKAN."""


ACCIONES = "https://catalogodatos.gub.uy/api/3/action/"


def accion(nombre: str, **parametros) -> dict:
    """Llama una accion de la API de CKAN y devuelve `result`, o levanta si `success` es falso.

        accion("package_show", id="inia-precipitacion-temps-extremas-sg")

    **Sale a la red.** El `User-Agent` y los reintentos los pone `uydatos.red`. Se le pasan los
    parametros tal como los espera CKAN (`q`, `fq`, `rows`, `facet.field`, ...) en vez de armar la
    consulta a mano: la sintaxis de `q` es una trampa medida (ver `buscar()`).
    """
    import urllib.parse

    url = f"{ACCIONES}{nombre}?{urllib.parse.urlencode(parametros)}"
    crudo = json.loads(red.pedir(url).decode("utf-8"))
    if not crudo.get("success"):
        raise CatalogoInvalido(
            f"{nombre}: el catalogo respondio success={crudo.get('success')!r}: {crudo.get('error')}"
        )
    return crudo["result"]


def parsear_busqueda(resultado: dict) -> dict:
    """De un `result` de `package_search`, el conteo, los facets y los datasets.

    El `count` es la cantidad de datasets que cumplen la consulta ENTERA, no los de esta pagina:
    es el unico numero de la respuesta que se puede citar. `facets` trae las organizaciones y los
    formatos de toda la busqueda, tambien completos.
    """
    return {
        "total": resultado["count"],
        "organizaciones": resultado.get("facets", {}).get("organization", {}),
        "formatos": resultado.get("facets", {}).get("res_format", {}),
        "datasets": [
            {
                "nombre": d["name"],
                "titulo": d.get("title", ""),
                "organizacion": (d.get("organization") or {}).get("name", ""),
                "modificado": d.get("metadata_modified", ""),
                "formatos": sorted({(r.get("format") or "").upper() for r in d.get("resources", [])}),
            }
            for d in resultado["results"]
        ],
    }


def buscar(
    texto: str = "",
    *,
    organizacion: Optional[str] = None,
    formato: Optional[str] = None,
    filas: int = 10,
    desde: int = 0,
) -> dict:
    """Busca datasets. `texto` es libre; `organizacion` y `formato` se filtran por campo.

    **Sale a la red.** No buscar por etiqueta con `texto`: medido el 2026-10-09,
    `fq=tags:clima` devuelve **0** (la etiqueta no existe, no es que no haya datos) mientras
    `fq=organization:inumet` devuelve **7**. Un 0 de una busqueda no es un dato hasta probarlo con
    otra consulta.
    """
    partes = []
    if organizacion:
        partes.append(f"organization:{organizacion}")
    if formato:
        partes.append(f"res_format:{formato.upper()}")
    parametros = {
        "q": texto,
        "rows": max(1, min(filas, 100)),
        "start": max(0, desde),
        "facet.field": '["organization", "res_format"]',
    }
    if partes:
        parametros["fq"] = " ".join(partes)
    return parsear_busqueda(accion("package_search", **parametros))


def datastore_search(recurso: str, *, limite: int = 100, desde: int = 0) -> dict:
    """Consulta las filas de un recurso ya cargado en el datastore de CKAN. **Sale a la red.**

    Medido el 2026-10-09 sobre el recurso de temperatura de INUMET (`f800fc53...`): `total`
    332.071 y campos `_id`, `fecha`, `estacion_id`, `temp_aire`. **Todos los campos vuelven como
    texto** y `total` incluye la fila del encabezado: quien los use tiene que convertir y
    descontar. No todos los recursos estan cargados en el datastore.
    """
    r = accion("datastore_search", resource_id=recurso, limit=max(1, min(limite, 1000)), offset=max(0, desde))
    return {
        "total": r["total"],
        "campos": [f["id"] for f in r.get("fields", [])],
        "filas": r.get("records", []),
    }


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
    url = f"{API}?{red.codificar({'id': dataset})}"
    return parsear_package_show(json.loads(red.pedir(url).decode("utf-8")))


def bajar_recurso(url: str, destino: Path) -> Path:
    """Baja un recurso a `destino`. **Sale a la red.**"""
    return red.bajar(url, destino)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m uydatos.catalogo", description=__doc__.splitlines()[0])
    ap.add_argument("dataset")
    args = ap.parse_args(argv)
    for r in recursos(args.dataset):
        print(f"{r['formato']:5} {r['modificado'][:10]}  {r['nombre']}\n      {r['url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
