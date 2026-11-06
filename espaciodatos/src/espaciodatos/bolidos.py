"""Bólidos registrados por sensores del gobierno de EE.UU. (CNEOS, JPL Fireball Data API).

Abierto, sin token. Medido el 2026-11-06 (hora de Uruguay), versión `1.2`, consulta completa
sin filtros: **1.074 bólidos** de 1988-04-15 a 2026-10-04, 76.456 bytes, sha256
`6bfc721f21c85e2f…`.

Las trampas, cada una con su número:

- **La latitud y la longitud vienen sin signo**, con el hemisferio en otra columna (`lat-dir` N/S,
  `lon-dir` E/W). Medido: 0 valores con signo en 888 ubicaciones. Si se ignora la dirección,
  la caja de Uruguay (29-36 °S, 52-60 °W) tiene **4 bólidos**; con la dirección, **uno solo**:
  2008-04-07 01:02:28 UTC, 31,8 °S 58,5 °W (a la altura de Salto y Concordia), 0,076 kt.
  Leído con signo positivo, ese bólido cae en Irán.
- **La ubicación es todo o nada**: 186 de 1.074 (17 %) sin ninguno de los cuatro campos, como
  dice la documentación. Una ubicación a medias se rechaza.
- **La altura y la velocidad faltan mucho más**: `alt` nulo en 472 (44 %), `vel` en 711 (66 %).
  Nulo, nunca cero.
- **El orden por defecto es descendente** (el más reciente primero) aunque el parámetro `sort`
  documenta ascendente por defecto. El lector ordena ascendente por fecha.
- **Dos energías con unidades distintas**: `energy` es la energía radiada en 10¹⁰ J y `impact-e`
  la energía de impacto estimada en kilotones. El máximo de `impact-e` es **441 kt** (Chelyabinsk,
  2013-02-15 03:20:26). El lector las devuelve con la unidad en el nombre.
- **`count` es un string** (`"1074"`), no un entero como en CAD.

Uso:

    python -m espaciodatos bolidos bajar datos/bolidos.json
    python -m espaciodatos bolidos cerca datos/bolidos.json --lat -32.5 --lon -56 --radio 600
"""

from __future__ import annotations

import argparse
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

from uydatos import procedencia

from espaciodatos import _jpl
from espaciodatos._jpl import JplInvalido

URL = f"{_jpl.BASE}/fireball.api"
FUENTE = "NASA/JPL Fireball Data API"
VERSION = "1.2"
CAMPOS = ["date", "energy", "impact-e", "lat", "lat-dir", "lon", "lon-dir", "alt", "vel"]
RADIO_TIERRA_KM = 6371.0


class BolidoInvalido(JplInvalido):
    """La respuesta de Fireball no cumple el contrato medido."""


def _coordenada(valor, direccion, negativa: str, positiva: str, tope: float, campo: str, donde: str) -> float:
    v = _jpl.numero(valor, campo, donde)
    if v < 0:
        raise BolidoInvalido(
            f"{donde}: {campo} {valor!r} con signo; el API manda el valor sin signo y el hemisferio aparte, "
            "y un valor con signo y dirección a la vez se invertiría dos veces"
        )
    if v > tope:
        raise BolidoInvalido(f"{donde}: {campo} {v} mayor que {tope}")
    if direccion not in (negativa, positiva):
        raise BolidoInvalido(f"{donde}: {campo}-dir {direccion!r}; se esperaba {negativa} o {positiva}")
    return -v if direccion == negativa else v


def _fila(f: dict, donde: str) -> dict:
    try:
        cuando = datetime.strptime(f["date"], "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        raise BolidoInvalido(f"{donde}: date {f['date']!r} ilegible; el API manda 2013-02-15 03:20:26") from None
    ubic = [f["lat"], f["lat-dir"], f["lon"], f["lon-dir"]]
    if all(x is None for x in ubic):
        lat = lon = None
    elif any(x is None for x in ubic):
        raise BolidoInvalido(f"{donde}: ubicación a medias {ubic}; la documentación y lo medido dicen todo o nada")
    else:
        lat = _coordenada(f["lat"], f["lat-dir"], "S", "N", 90, "lat", donde)
        lon = _coordenada(f["lon"], f["lon-dir"], "W", "E", 180, "lon", donde)
    n = _jpl.numero
    energia = n(f["energy"], "energy", donde)
    impacto = n(f["impact-e"], "impact-e", donde)
    if energia <= 0 or impacto <= 0:
        raise BolidoInvalido(f"{donde}: energía {energia} o impacto {impacto} no positivos")
    return {
        "instante_utc": cuando,
        "lat": lat,
        "lon": lon,
        "alt_km": n(f["alt"], "alt", donde, nulo=True),
        "vel_kms": n(f["vel"], "vel", donde, nulo=True),
        "energia_radiada_j": energia * 1e10,
        "energia_impacto_kt": impacto,
    }


def leer(ruta: Path) -> list[dict]:
    """Los bólidos de un archivo bajado, tipados, con signo, y ordenados por fecha ascendente."""
    ruta = Path(ruta)
    d = _jpl.cargar(ruta)
    _jpl.firma(d, FUENTE, VERSION, ruta.name)
    datos = _jpl.campos(d, CAMPOS, ruta.name)
    _jpl.cuenta(d, datos, ruta.name)
    filas = [_fila(dict(zip(CAMPOS, c)), f"{ruta.name} fila {i}") for i, c in enumerate(datos)]
    filas.sort(key=lambda b: b["instante_utc"])
    return filas


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia de gran círculo (haversine, esfera de 6.371 km)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * RADIO_TIERRA_KM * math.asin(math.sqrt(a))


def cerca(filas: list[dict], lat: float, lon: float, radio_km: float) -> list[dict]:
    """Los bólidos con ubicación a menos de `radio_km` del punto, con la distancia agregada.
    Los que no tienen ubicación **no** se cuentan como lejanos: se dejan afuera y se dice cuántos."""
    out = []
    for b in filas:
        if b["lat"] is None:
            continue
        d = distancia_km(lat, lon, b["lat"], b["lon"])
        if d <= radio_km:
            out.append({**b, "distancia_km": d})
    return out


def resumen(filas: list[dict]) -> dict:
    if not filas:
        raise BolidoInvalido("resumen() necesita al menos una fila")
    mayor = max(filas, key=lambda b: b["energia_impacto_kt"])
    return {
        "filas": len(filas),
        "primero": filas[0]["instante_utc"],
        "ultimo": filas[-1]["instante_utc"],
        "sin_ubicacion": sum(b["lat"] is None for b in filas),
        "sin_altura": sum(b["alt_km"] is None for b in filas),
        "sin_velocidad": sum(b["vel_kms"] is None for b in filas),
        "mayor": mayor,
    }


def descargar(destino: Path) -> Path:
    """Baja la serie completa a `destino`. **Sale a la red.**"""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(_jpl.pedir(URL))
    return destino


def sello(ruta: Path, *, filas: Optional[int] = None) -> procedencia.Sello:
    version = _jpl.firma(_jpl.cargar(ruta), FUENTE, VERSION, Path(ruta).name)
    return procedencia.sello(f"JPL Fireball {version}", ruta=Path(ruta), url=URL, filas=filas)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m espaciodatos bolidos", description=__doc__.splitlines()[0])
    ap.add_argument("accion", choices=["bajar", "resumen", "cerca"])
    ap.add_argument("ruta", type=Path)
    ap.add_argument("--lat", type=float, default=-32.5, help="por defecto, el centro de Uruguay")
    ap.add_argument("--lon", type=float, default=-56.0)
    ap.add_argument("--radio", type=float, default=600.0, help="km")
    args = ap.parse_args(argv)
    if args.accion == "bajar":
        print(descargar(args.ruta))
        return 0
    filas = leer(args.ruta)
    if args.accion == "cerca":
        cercanos = cerca(filas, args.lat, args.lon, args.radio)
        sin = sum(b["lat"] is None for b in filas)
        print(
            f"{len(cercanos)} bólidos a menos de {args.radio:.0f} km de ({args.lat}, {args.lon}); "
            f"{sin} sin ubicación, que no se cuentan"
        )
        for b in cercanos:
            print(
                f"  {b['instante_utc']:%Y-%m-%d %H:%M:%S} UTC  {b['lat']:.1f}, {b['lon']:.1f}  "
                f"a {b['distancia_km']:.0f} km  {b['energia_impacto_kt']} kt"
            )
    else:
        r = resumen(filas)
        print(f"{r['filas']} bólidos, {r['primero']:%Y-%m-%d} a {r['ultimo']:%Y-%m-%d}")
        print(
            f"  sin ubicación {r['sin_ubicacion']} · sin altura {r['sin_altura']} · sin velocidad {r['sin_velocidad']}"
        )
        m = r["mayor"]
        print(f"  el mayor: {m['instante_utc']:%Y-%m-%d %H:%M:%S} UTC, {m['energia_impacto_kt']} kt")
    print(procedencia.como_linea(sello(args.ruta, filas=len(filas))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
