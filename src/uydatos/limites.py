"""Límites oficiales: los departamentos y las localidades del INE, y en cuál cae un punto.

`ideuy.reverse` no alcanza para decir en qué departamento está un punto: devuelve **la dirección
más cercana, esté donde esté**. Medido el 10/10/2026: un punto en el mar, a unos 200 km de la
costa, devolvió "LOS TORDOS 15, MALDONADO". Cerca de un límite departamental, o en el campo, la
dirección más cercana puede ser de otro departamento. Para responder "¿en qué departamento cae?"
hacen falta los polígonos.

Las capas, servidas por WFS en GeoJSON:

- `departamentos`: los límites del INE, publicados por la IDE (`INE_NO_SEGURO:ine_depto`).
- `localidades`: las 652 localidades del INE, publicadas por el MIDES (`INECenso:Localidades_pg`),
  con población y viviendas en los campos `pob_tot_23` y `viv_tot_23`. **El 2023 sale del nombre
  del campo**, no de un metadato.

Las trampas
-----------
1. **La capa de departamentos trae 20 polígonos, no 19.** El vigésimo se llama "LIMITE
   CONTESTADO": la zona en disputa con Brasil al norte de Artigas, y **lleva el código (2) y el ISO
   (`UYAR`) de Artigas**. Contarlos como departamentos da 20, y exigir un código por polígono la
   rechaza. Se devuelve con `tipo = "limite_contestado"` y `departamento = "ARTIGAS"`.
2. **Sin `srsName=EPSG:4326` el servicio contesta en UTM 21S, en metros.** Un punto en grados
   nunca cae adentro de un polígono en metros, y no da error: da "fuera de todo". Una coordenada
   fuera de los grados posibles se rechaza.
3. **Una respuesta de error del WFS viene en XML**, con HTTP 200. Se rechaza al leer.
4. **Los polígonos tienen agujeros** (anillos interiores). Un punto en un agujero no está adentro.

`mas_cercana` mide hasta el vértice más cercano de cada polígono, no hasta el borde exacto: con la
densidad de vértices de estas capas la diferencia es de metros, y así no hace falta una librería
de geometría.

Uso:
    python -m uydatos.limites bajar departamentos datos/departamentos.geojson
    python -m uydatos.limites ubicar datos/departamentos.geojson departamentos -31.38 -57.96
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Optional, Sequence

from uydatos import red

_WFS = "service=WFS&version=1.0.0&request=GetFeature&outputFormat=application/json&srsName=EPSG:4326"

CAPAS: dict[str, dict] = {
    "departamentos": {
        "url": f"https://mapas.ide.uy/geoserver-vectorial/INE_NO_SEGURO/wfs?{_WFS}&typeName=ine_depto",
        "fuente": "INE, límites departamentales, publicados por la IDE (mapas.ide.uy)",
        "codigo": "depto",
        "nombre": "nombre",
        "departamento": "nombre",
        "datos": {"iso": "cdepto_iso"},
    },
    "localidades": {
        "url": f"https://mapas.mides.gub.uy/geoserver/ows?{_WFS}&typeName=INECenso:Localidades_pg",
        "fuente": "INE, localidades, publicadas por el MIDES (mapas.mides.gub.uy)",
        "codigo": "CODLOC",
        "nombre": "NOMBLOC",
        "departamento": "NOMBDEPTO",
        "datos": {"poblacion_2023": "pob_tot_23", "viviendas_2023": "viv_tot_23", "capital": "capital"},
    },
}

TIPO = {"departamentos": "departamento", "localidades": "localidad"}
DEPARTAMENTOS = 19
CONTESTADO = "LIMITE CONTESTADO"

# Grados posibles en Uruguay, con margen. Fuera de esto la capa no está en EPSG:4326.
_LAT = (-36.0, -29.5)
_LON = (-59.0, -52.5)


class LimitesInvalido(ValueError):
    """La capa no cumple el contrato de la fuente."""


def _poligonos(geom: dict, donde: str) -> list:
    if not geom or geom.get("type") not in ("Polygon", "MultiPolygon"):
        raise LimitesInvalido(f"{donde}: geometría {geom.get('type') if geom else None}, se esperaba un polígono")
    polis = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    for poli in polis:
        for anillo in poli:
            for lon, lat, *_ in anillo:
                if not (_LAT[0] <= lat <= _LAT[1] and _LON[0] <= lon <= _LON[1]):
                    raise LimitesInvalido(
                        f"{donde}: coordenada ({lon}, {lat}) fuera de Uruguay. Si son números grandes, la capa vino "
                        "en metros (UTM 21S): hay que pedirla con srsName=EPSG:4326."
                    )
    return polis


def leer(capa: str, ruta: Path) -> list[dict]:
    """Lee una capa bajada. Cada área: `codigo`, `nombre`, `departamento`, `tipo`, `datos`, `bbox`
    (lon_min, lat_min, lon_max, lat_max) y `poligonos` (MultiPolygon en grados, lon/lat)."""
    if capa not in CAPAS:
        raise LimitesInvalido(f"capa {capa!r}: {', '.join(CAPAS)}")
    c, ruta = CAPAS[capa], Path(ruta)
    try:
        crudo = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise LimitesInvalido(f"{ruta.name}: no es GeoJSON (un error del WFS viene en XML con HTTP 200): {e}") from None
    if crudo.get("type") != "FeatureCollection" or not crudo.get("features"):
        raise LimitesInvalido(f"{ruta.name}: no es una FeatureCollection con elementos")
    areas, codigos = [], set()
    for i, f in enumerate(crudo["features"]):
        p = f.get("properties") or {}
        faltan = [v for v in (c["codigo"], c["nombre"], c["departamento"], *c["datos"].values()) if v not in p]
        if faltan:
            raise LimitesInvalido(f"{ruta.name} elemento {i}: faltan los campos {faltan}")
        nombre = str(p[c["nombre"]]).strip()
        contestado = capa == "departamentos" and nombre == CONTESTADO
        if not contestado:
            if p[c["codigo"]] in codigos:
                raise LimitesInvalido(f"{ruta.name}: código {p[c['codigo']]} repetido")
            codigos.add(p[c["codigo"]])
        polis = _poligonos(f.get("geometry"), f"{ruta.name} elemento {i}")
        puntos = [pt for poli in polis for anillo in poli for pt in anillo]
        areas.append(
            {
                "codigo": p[c["codigo"]],
                "nombre": nombre,
                "departamento": str(p[c["departamento"]]).strip(),
                "tipo": "limite_contestado" if contestado else TIPO[capa],
                "datos": {k: p[v] for k, v in c["datos"].items()},
                "bbox": (
                    min(x[0] for x in puntos),
                    min(x[1] for x in puntos),
                    max(x[0] for x in puntos),
                    max(x[1] for x in puntos),
                ),
                "poligonos": polis,
            }
        )
    if capa == "departamentos":
        n = sum(1 for a in areas if a["tipo"] == "departamento")
        if n != DEPARTAMENTOS:
            raise LimitesInvalido(f"{ruta.name}: {n} departamentos, Uruguay tiene {DEPARTAMENTOS}")
        por_codigo = {a["codigo"]: a["nombre"] for a in areas if a["tipo"] == "departamento"}
        for a in areas:
            if a["tipo"] == "limite_contestado":
                a["departamento"] = por_codigo.get(a["codigo"], a["departamento"])
    return areas


def _en_anillo(lat: float, lon: float, anillo: list) -> bool:
    """Par-impar (ray casting) sobre un anillo de (lon, lat)."""
    adentro, j = False, len(anillo) - 1
    for i in range(len(anillo)):
        xi, yi = anillo[i][0], anillo[i][1]
        xj, yj = anillo[j][0], anillo[j][1]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            adentro = not adentro
        j = i
    return adentro


def contiene(area: dict, lat: float, lon: float) -> bool:
    """¿El punto está adentro del área? Un punto en un agujero no está adentro."""
    x0, y0, x1, y1 = area["bbox"]
    if not (x0 <= lon <= x1 and y0 <= lat <= y1):
        return False
    for poli in area["poligonos"]:
        if _en_anillo(lat, lon, poli[0]) and not any(_en_anillo(lat, lon, hueco) for hueco in poli[1:]):
            return True
    return False


def ubicar(areas: list[dict], lat: float, lon: float) -> Optional[dict]:
    """El área que contiene el punto, o None (en el mar, en el río, fuera de toda localidad)."""
    return next((a for a in areas if contiene(a, lat, lon)), None)


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = math.radians
    a = math.sin(r(lat2 - lat1) / 2) ** 2 + math.cos(r(lat1)) * math.cos(r(lat2)) * math.sin(r(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(a))


def mas_cercana(areas: list[dict], lat: float, lon: float) -> tuple[dict, float]:
    """El área más cercana y la distancia aproximada en km hasta su vértice más cercano."""
    if not areas:
        raise LimitesInvalido("no hay áreas para comparar")
    mejor, mejor_km = areas[0], float("inf")
    for a in areas:
        for poli in a["poligonos"]:
            for lon_v, lat_v, *_ in poli[0]:
                d = distancia_km(lat, lon, lat_v, lon_v)
                if d < mejor_km:
                    mejor, mejor_km = a, d
    return mejor, mejor_km


def descargar(capa: str, destino: Path) -> Path:
    """Baja una capa en GeoJSON, en grados (EPSG:4326). **Sale a la red.** Son unos 5 MB cada una."""
    if capa not in CAPAS:
        raise LimitesInvalido(f"capa {capa!r}: {', '.join(CAPAS)}")
    return red.bajar(CAPAS[capa]["url"], Path(destino))


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m uydatos.limites", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="orden", required=True)
    b = sub.add_parser("bajar")
    b.add_argument("capa", choices=sorted(CAPAS))
    b.add_argument("destino", type=Path)
    u = sub.add_parser("ubicar", help="en qué área cae un punto")
    u.add_argument("archivo", type=Path)
    u.add_argument("capa", choices=sorted(CAPAS))
    u.add_argument("lat", type=float)
    u.add_argument("lon", type=float)
    args = ap.parse_args(argv)
    if args.orden == "bajar":
        print(f"bajado {descargar(args.capa, args.destino)}")
        return 0
    areas = leer(args.capa, args.archivo)
    a = ubicar(areas, args.lat, args.lon)
    if a:
        print(f"adentro de {a['nombre']} ({a['departamento']}) {a['datos']}")
    else:
        a, km = mas_cercana(areas, args.lat, args.lon)
        print(f"fuera de toda área; la más cercana es {a['nombre']} ({a['departamento']}), a ~{km:.1f} km")
    return 0


if __name__ == "__main__":
    sys.exit(main())
