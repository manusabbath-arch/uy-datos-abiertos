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


def variantes_de_formato(formato: str) -> list[str]:
    """Los valores de `res_format` del catálogo que son `formato` sin importar mayúsculas.

    **Sale a la red** (una búsqueda sin filas, solo con el facet). El filtro de CKAN distingue
    mayúsculas y el catálogo mezcla: medido el 10/10/2026, 21 recursos «GeoJSON» y ninguno «GEOJSON»;
    «csv zip» junto a «CSV ZIP». Si no aparece ninguno se devuelve el formato en mayúsculas, que es lo
    más común, y la búsqueda dará 0 por un motivo real.
    """
    r = accion("package_search", rows=0, **{"facet.field": '["res_format"]', "facet.limit": "-1"})
    existentes = (r.get("facets") or {}).get("res_format") or {}
    variantes = sorted(f for f in existentes if f.strip().lower() == formato.strip().lower())
    return variantes or [formato.upper()]


def _filtro_formato(variantes: list[str]) -> str:
    def citar(v: str) -> str:
        return f'"{v}"' if any(c in v for c in ' ():"') else v

    if len(variantes) == 1:
        return f"res_format:{citar(variantes[0])}"
    return "res_format:(" + " OR ".join(f'"{v}"' for v in variantes) + ")"


def formatos() -> dict[str, int]:
    """El histograma de `res_format` de TODO el catálogo. **Sale a la red.**

    El facet viene completo aunque `rows=0`, así que no hay que paginar para contar formatos: una
    sola petición. Medido el 2026-10-17 sobre 2.777 datasets.
    """
    r = accion(
        "package_search",
        q="*:*",
        rows=0,
        **{"facet.field": '["res_format"]', "facet.limit": "-1"},
    )
    return dict((r.get("facets") or {}).get("res_format") or {})


def nombres() -> list[str]:
    """Los nombres de dataset de `package_list`. **Sale a la red.**

    Medido el 2026-10-17: 2.777. El 2026-10-09 eran 2.779: el total **puede bajar**, así que un
    test que lo afirme como piso también envejece.
    """
    r = accion("package_list")
    if not isinstance(r, list) or not r:
        raise CatalogoInvalido(f"package_list devolvió {type(r).__name__} vacío, se esperaba una lista de nombres")
    return r


def todos(por_pagina: int = 1000) -> list[str]:
    """Los nombres de dataset que devuelve `package_search`, paginando. **Sale a la red.**

    Medido el 2026-10-17: 2.716, contra 2.777 de `package_list`. El buscador no ve el catálogo
    entero; la diferencia se pide con `faltantes()`.
    """
    nombres: list[str] = []
    anterior: Optional[list[str]] = None
    while True:
        r = accion("package_search", q="*:*", rows=por_pagina, start=len(nombres))
        total = r.get("count")
        if not isinstance(total, int):
            raise CatalogoInvalido(f"package_search sin un `count` entero: {total!r}")
        pagina = [d["name"] for d in r.get("results", [])]
        if not pagina:
            break
        if pagina == anterior:
            raise CatalogoInvalido(
                f"package_search devolvió la misma página dos veces en start={len(nombres)}: "
                f"{len(nombres)} nombres de {total}"
            )
        anterior = pagina
        nombres.extend(pagina)
        if len(nombres) >= total:
            break
    return nombres


def faltantes() -> dict:
    """Qué datasets de `package_list` no aparecen en `package_search`. **Sale a la red.**

    Los dos endpoints del mismo catálogo no cuentan lo mismo: medido el 2026-10-17, 2.777 contra
    2.716. Si la búsqueda devolviera un nombre que la lista no tiene, el catálogo cambió de forma y
    se rechaza en vez de devolver una diferencia con signo raro.
    """
    en_lista = set(nombres())
    en_busqueda = set(todos())
    sobra = sorted(en_busqueda - en_lista)
    if sobra:
        raise CatalogoInvalido(
            f"package_search devolvió {len(sobra)} datasets que no están en package_list: {sobra[:3]}"
        )
    return {
        "en_lista": len(en_lista),
        "en_busqueda": len(en_busqueda),
        "faltan": sorted(en_lista - en_busqueda),
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
        partes.append(_filtro_formato(variantes_de_formato(formato)))
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
    ap.add_argument("dataset", nargs="?", help="el id de un dataset, para ver sus recursos")
    ap.add_argument("--formatos", action="store_true", help="el histograma de formatos de todo el catálogo")
    ap.add_argument("--faltantes", action="store_true", help="los datasets que el buscador no ve")
    args = ap.parse_args(argv)
    if args.formatos:
        for formato, cuantos in sorted(formatos().items(), key=lambda kv: -kv[1]):
            print(f"{cuantos:>6}  {formato}")
        return 0
    if args.faltantes:
        r = faltantes()
        print(f"en_lista {r['en_lista']} · en_busqueda {r['en_busqueda']} · faltan {len(r['faltan'])}")
        print("\n".join(r["faltan"]))
        return 0
    if not args.dataset:
        ap.print_help()
        return 2
    for r in recursos(args.dataset):
        print(f"{r['formato']:5} {r['modificado'][:10]}  {r['nombre']}\n      {r['url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
