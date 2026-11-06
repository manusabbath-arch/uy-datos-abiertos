"""Acercamientos de asteroides y cometas a la Tierra (JPL SBDB Close Approach Data API, `cad.api`).

Abierto, sin token. Medido el 2026-11-06 (hora de Uruguay) con la consulta completa
`date-min=1900-01-01&date-max=2200-01-01&dist-max=0.05&fullname=true&diameter=true`:
**52.247 acercamientos de 20.248 objetos**, 10.740.795 bytes, sha256 `691ce8c490321b7a…`,
versión `1.5`. 18.680 son futuros; 1.752 a menos de una distancia lunar (107 futuros, contados por `jd`).

Las trampas, cada una con su número:

- **Todo número es un string** (`"0.00963195025335591"`), y `count` es un entero (`52247`)
  mientras que en Sentry y Fireball es un string.
- **La fecha `cd` (`"1900-Jan-04 22:25"`) no se ordena como texto**: el mínimo de las 52.247
  como string es `"1900-Apr-03 19:19"`, y el primer acercamiento es del 4 de enero. El lector
  ordena por `jd`. Medido en carne propia: contando "futuros a menos de 1 LD" con `cd > "2026"`
  como texto dio 246; por `jd`, son 107. Tampoco se lee con `strptime("%b")`, que depende del *locale* (con `es_UY`
  "Jan" no existe): los meses van en una tabla propia.
- **La escala es TDB, no UTC** (lo dice la documentación de `jd` y `cd`). Medido: `cd` y `jd`
  coinciden en las 52.247 filas con una diferencia máxima de 30 s (el redondeo al minuto), y
  TDB−UTC es ~69 s hoy: **al minuto no cambia nada**, pero el instante se entrega etiquetado
  como TDB y no como UTC.
- **La incertidumbre `t_sigma_f` tiene tres formatos**: `"< 00:01"` (19.886 filas), `"HH:MM"`
  (19.042) y `"D_HH:MM"` con días (13.319, hasta `9_17:20`). Se entrega en minutos, con la cota
  `"<"` marcada aparte.
- **`dist_min = 0` no es un impacto posible**: 14 filas, varias en el pasado (2008 EK68 el
  2008-03-03, 2012 HA34 en **1945**, un objeto descubierto en 2012). Es el mínimo 3σ recortado en
  cero en órbitas muy inciertas. Se marca como `dist_min_en_cero`, no se interpreta.
- **Los acercamientos del pasado de objetos descubiertos después son cálculo, no observación**:
  2012 HA34 "pasó" en 1945 según su órbita actual.
- **`v_inf` nulo**: 27 filas, todas de objetos conocidos como minilunas o capturas temporales
  (2020 CD3 ×14, 2006 RH120 ×5, 2024 GB15 ×3, 2026 QQ8 ×2, 2012 TF79, 2022 NX1, 2023 HG11): la
  velocidad hiperbólica no está definida mientras la órbita está ligada a la Tierra. Pero 2020 CD3
  la trae nula también en **2044 y 2061**, fuera de su captura de 2017-2020, y con valor en 1985 y
  1986. El lector no lo explica: lo marca como `sin_v_inf` y no lo rellena.
- **`h` nulo = cometa**: 10 filas, todas cometas (`289P/Blanpain`, `7P/Pons-Winnecke`...). Un
  `h` nulo en algo que no es cometa se rechaza.
- **El diámetro es nulo en el 97 %** (50.758 de 52.247): sólo hay diámetro medido para 1.489
  filas, y en una (8014, 1990 MF) viene el diámetro sin su sigma. El lector no lo estima desde
  `h`: un diámetro inventado con un albedo supuesto es otra cosa (ver `sentry`).
- **La ventana por defecto del API es de 60 días y 0,05 au**: una consulta sin fechas no trae
  "todos". El lector siempre pide fechas explícitas.
- **El API no declara cuánto vale una distancia lunar**: `dist-max=1LD` y `dist-max=0.0025695`
  traen lo mismo (140 acercamientos en 2026, medido). El lector usa 384.400 km / 1 au.
- **Una consulta sin resultados no trae `fields` ni `data`**: sólo `{"count":0, "signature":…}`.

Uso:

    python -m espaciodatos cad bajar datos/cad.json --desde 1900-01-01 --hasta 2200-01-01
    python -m espaciodatos cad resumen datos/cad.json
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional, Sequence

from uydatos import procedencia, red

from espaciodatos import _jpl
from espaciodatos._jpl import JplInvalido

URL = f"{_jpl.BASE}/cad.api"
FUENTE = "NASA/JPL SBDB Close Approach Data API"
VERSION = "1.5"
CAMPOS = [
    "des",
    "orbit_id",
    "jd",
    "cd",
    "dist",
    "dist_min",
    "dist_max",
    "v_rel",
    "v_inf",
    "t_sigma_f",
    "h",
    "diameter",
    "diameter_sigma",
    "fullname",
]

KM_POR_AU = 149_597_870.7  # IAU 2012
KM_POR_LD = 384_400.0
AU_POR_LD = KM_POR_LD / KM_POR_AU  # 0.0025695...

_MESES = {m: i for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), start=1)}
_CD = re.compile(r"^(\d{4})-([A-Z][a-z]{2})-(\d{2}) (\d{2}):(\d{2})$")
_T_SIGMA = re.compile(r"^(<\s)?(?:(\d+)_)?(\d{2}):(\d{2})$")


class CadInvalido(JplInvalido):
    """La respuesta de CAD no cumple el contrato medido."""


def url(desde: date, hasta: date, *, dist_max_au: float = 0.05) -> str:
    """La consulta con fechas explícitas y los campos opcionales que el lector exige. No sale a la red."""
    if not desde < hasta:
        raise CadInvalido(f"desde={desde} no es anterior a hasta={hasta}; el API responde count 0 sin error")
    if not 0 < dist_max_au <= 1:
        raise CadInvalido(f"dist_max_au={dist_max_au}: fuera de 0 a 1 au")
    params = {
        "date-min": desde.isoformat(),
        "date-max": hasta.isoformat(),
        "dist-max": repr(dist_max_au),
        "fullname": "true",
        "diameter": "true",
    }
    return f"{URL}?{red.codificar(params)}"


def instante_tdb(cd: str, donde: str = "cd") -> datetime:
    """`"2029-Apr-13 21:46"` como `datetime` sin zona, **en TDB**. Sin `strptime("%b")`."""
    m = _CD.match(cd or "")
    if not m or m.group(2) not in _MESES:
        raise CadInvalido(f"{donde}: fecha {cd!r} ilegible; el API manda 2029-Apr-13 21:46")
    a, mes, d, hh, mm = m.groups()
    return datetime(int(a), _MESES[mes], int(d), int(hh), int(mm))


def t_sigma_minutos(texto: str, donde: str = "t_sigma_f") -> tuple[int, bool]:
    """La incertidumbre 3σ del instante en minutos, y si es una cota superior (`"< 00:01"`)."""
    m = _T_SIGMA.match(texto or "")
    if not m:
        raise CadInvalido(
            f"{donde}: t_sigma_f {texto!r} fuera de los tres formatos medidos ('< 00:01', '13:02', '2_09:08')"
        )
    cota, dias, hh, mm = m.groups()
    return (int(dias or 0) * 1440 + int(hh) * 60 + int(mm), cota is not None)


def _es_cometa(fullname: str) -> bool:
    return "/" in fullname


def _fila(f: dict, donde: str) -> dict:
    n = _jpl.numero
    dist = n(f["dist"], "dist", donde)
    dmin = n(f["dist_min"], "dist_min", donde)
    dmax = n(f["dist_max"], "dist_max", donde)
    if not (0 <= dmin <= dist <= dmax):
        raise CadInvalido(f"{donde}: no se cumple 0 <= dist_min <= dist <= dist_max ({dmin}, {dist}, {dmax})")
    if dist <= 0:
        raise CadInvalido(f"{donde}: distancia nominal {dist} au; un acercamiento a distancia cero es un impacto")
    nombre = (f["fullname"] or "").strip()
    h = n(f["h"], "h", donde, nulo=True)
    if h is None and not _es_cometa(nombre):
        raise CadInvalido(f"{donde}: {nombre!r} sin h y no es cometa; en lo medido sólo los cometas no traen h")
    v_rel = n(f["v_rel"], "v_rel", donde)
    if v_rel <= 0:
        raise CadInvalido(f"{donde}: v_rel {v_rel} km/s; una velocidad relativa no es cero ni negativa")
    v_inf = n(f["v_inf"], "v_inf", donde, nulo=True)
    diametro = n(f["diameter"], "diameter", donde, nulo=True)
    sigma_d = n(f["diameter_sigma"], "diameter_sigma", donde, nulo=True)
    if diametro is None and sigma_d is not None:
        raise CadInvalido(f"{donde}: trae diameter_sigma sin diameter")
    minutos, cota = t_sigma_minutos(f["t_sigma_f"], donde)
    return {
        "des": f["des"],
        "nombre": nombre,
        "orbita": f["orbit_id"],
        "jd_tdb": n(f["jd"], "jd", donde),
        "instante_tdb": instante_tdb(f["cd"], donde),
        "dist_au": dist,
        "dist_min_au": dmin,
        "dist_max_au": dmax,
        "dist_ld": dist / AU_POR_LD,
        "dist_km": dist * KM_POR_AU,
        "v_rel_kms": v_rel,
        "v_inf_kms": v_inf,
        "t_sigma_min": minutos,
        "t_sigma_es_cota": cota,
        "h": h,
        "diametro_km": diametro,
        "diametro_sigma_km": sigma_d,
        # Lo que no se interpreta, se marca:
        "cometa": _es_cometa(nombre),
        "sin_v_inf": v_inf is None,
        "dist_min_en_cero": dmin == 0,
    }


def leer(ruta: Path) -> list[dict]:
    """Los acercamientos de un archivo bajado, tipados y ordenados por `jd`. No sale a la red."""
    ruta = Path(ruta)
    d = _jpl.cargar(ruta)
    _jpl.firma(d, FUENTE, VERSION, ruta.name)
    if "fields" not in d and d.get("count") in (0, "0"):
        return []  # la respuesta vacía no trae fields ni data (medido)
    datos = _jpl.campos(d, CAMPOS, ruta.name)
    _jpl.cuenta(d, datos, ruta.name)
    filas = [_fila(dict(zip(CAMPOS, crudo)), f"{ruta.name} fila {i}") for i, crudo in enumerate(datos)]
    filas.sort(key=lambda x: x["jd_tdb"])
    return filas


def proximos(filas: list[dict], *, desde: datetime, dias: int = 30, max_ld: Optional[float] = None) -> list[dict]:
    """Los acercamientos de los próximos `dias` días desde `desde` (TDB; al minuto es UTC), por fecha."""
    hasta = desde + timedelta(days=dias)
    out = [f for f in filas if desde <= f["instante_tdb"] <= hasta]
    if max_ld is not None:
        out = [f for f in out if f["dist_ld"] <= max_ld]
    return out


def resumen(filas: list[dict], *, ahora: Optional[datetime] = None) -> dict:
    """Las cuentas que dejan ver las trampas: nulos, marcas y el acercamiento más cercano."""
    if not filas:
        raise CadInvalido("resumen() necesita al menos una fila")
    ahora = ahora or _jpl.ahora_utc()
    futuros = [f for f in filas if f["instante_tdb"] > ahora]
    return {
        "filas": len(filas),
        "objetos": len({f["des"] for f in filas}),
        "primero": filas[0]["instante_tdb"],
        "ultimo": filas[-1]["instante_tdb"],
        "futuros": len(futuros),
        "a_menos_de_1_ld": sum(f["dist_ld"] < 1 for f in filas),
        "futuros_a_menos_de_1_ld": sum(f["dist_ld"] < 1 for f in futuros),
        "sin_diametro": sum(f["diametro_km"] is None for f in filas),
        "cometas": sum(f["cometa"] for f in filas),
        "sin_v_inf": Counter(f["nombre"] for f in filas if f["sin_v_inf"]),
        "dist_min_en_cero": sum(f["dist_min_en_cero"] for f in filas),
        "incertidumbre_en_dias": sum(f["t_sigma_min"] >= 1440 for f in filas),
        "mas_cercano_futuro": min(futuros, key=lambda f: f["dist_au"]) if futuros else None,
    }


def descargar(destino: Path, desde: date, hasta: date, *, dist_max_au: float = 0.05) -> Path:
    """Baja la consulta a `destino`. **Sale a la red.**"""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(_jpl.pedir(url(desde, hasta, dist_max_au=dist_max_au)))
    return destino


def sello(ruta: Path, *, filas: Optional[int] = None) -> procedencia.Sello:
    """Fuente con la versión leída del archivo, fecha de la copia, sha256 y filas."""
    version = _jpl.firma(_jpl.cargar(ruta), FUENTE, VERSION, Path(ruta).name)
    return procedencia.sello(f"JPL CAD {version}", ruta=Path(ruta), url=URL, filas=filas)


def _texto(f: dict) -> str:
    d = f"{f['diametro_km'] * 1000:.0f} m" if f["diametro_km"] is not None else "diám. s/d"
    marcas = [m for m in ("sin_v_inf", "dist_min_en_cero", "cometa") if f[m]]
    cota = "<" if f["t_sigma_es_cota"] else "±"
    return (
        f"{f['instante_tdb']:%Y-%m-%d %H:%M} TDB {cota}{f['t_sigma_min']} min  {f['nombre']:<28} "
        f"{f['dist_ld']:7.2f} LD  {f['v_rel_kms']:5.1f} km/s  H {f['h'] if f['h'] is not None else 's/d'}  {d}"
        + (f"  [{', '.join(marcas)}]" if marcas else "")
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m espaciodatos cad", description=__doc__.splitlines()[0])
    ap.add_argument("accion", choices=["bajar", "resumen", "proximos"])
    ap.add_argument("ruta", type=Path)
    ap.add_argument("--desde", type=date.fromisoformat, default=date(1900, 1, 1))
    ap.add_argument("--hasta", type=date.fromisoformat, default=date(2200, 1, 1))
    ap.add_argument("--dias", type=int, default=30)
    ap.add_argument("--max-ld", type=float)
    args = ap.parse_args(argv)
    if args.accion == "bajar":
        print(descargar(args.ruta, args.desde, args.hasta))
        return 0
    filas = leer(args.ruta)
    if args.accion == "proximos":
        for f in proximos(filas, desde=_jpl.ahora_utc(), dias=args.dias, max_ld=args.max_ld):
            print(_texto(f))
    else:
        r = resumen(filas)
        print(f"{r['filas']} acercamientos de {r['objetos']} objetos, {r['primero']:%Y-%m-%d} a {r['ultimo']:%Y-%m-%d}")
        print(
            f"  futuros {r['futuros']} · a menos de 1 LD {r['a_menos_de_1_ld']} "
            f"({r['futuros_a_menos_de_1_ld']} futuros)"
        )
        print(f"  sin diámetro {r['sin_diametro']} · cometas {r['cometas']} · dist_min en cero {r['dist_min_en_cero']}")
        print(f"  incertidumbre de días {r['incertidumbre_en_dias']} · sin v_inf {dict(r['sin_v_inf'])}")
        if r["mas_cercano_futuro"]:
            print(f"  el más cercano por venir: {_texto(r['mas_cercano_futuro'])}")
    print(procedencia.como_linea(sello(args.ruta, filas=len(filas))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
