"""La lista de riesgo de impacto de la ESA (NEO Coordination Centre, `neo.ssa.esa.int`).

Abierta, sin token, en **texto de ancho fijo** separado por `|`. Medido el 2026-11-06 (hora de
Uruguay): **2.205 objetos**, 300.322 bytes, 2.209 líneas, sha256 `06195d4e7b555bcd…`, con
`Last Update: 2026-11-06 14:58 UTC` en la primera línea.

Las trampas, cada una con su número:

- **La designación va sin espacio** (`2008JL3`) y el único numerado de la lista va como número,
  quince espacios y la provisional pegada (`443104               2013XK22`). Contra el `des` de
  JPL no coincide ninguna sin normalizar (ver `designacion`).
- **El diámetro está en metros** (en JPL, en km), redondeado a entero salvo debajo de 10 m
  (71 con decimal), y la columna `*=Y` dice si es **estimado**: 2.196 lo son; 9 no.
- **El Torino tiene dos ausencias distintas**: `n/a` (20 filas) y `n/d` (5), las 25 con el
  impacto máximo en 2126. Medido: todos los `n/a` son anteriores al 2126-11-06 06:36 y todos los
  `n/d` posteriores al 2126-11-14. La ESA no documenta en el archivo la diferencia: el lector
  devuelve `None` y conserva el código crudo, sin interpretarlo.
- **El horizonte es de ~100 años** (impactos de 2026 a 2127). Sentry llega a **2880**: los dos
  objetos de mayor riesgo de JPL (Bennu y 1950 DA) **no están** en la lista de la ESA, y no por
  desacuerdo sino por horizonte. Ver `cruce`.
- **La probabilidad usa `E` mayúscula y dos dígitos** (`1.66E-4`, `8.11E-11`).
- **Cada fila termina con `|`**: 12 campos al partir, el último vacío. Una fila con otra cantidad
  se rechaza.

Uso:

    python -m espaciodatos esa bajar datos/esa_riesgo.txt
    python -m espaciodatos esa resumen datos/esa_riesgo.txt
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

from uydatos import procedencia, red
from uydatos.errores import DatosInvalidos

from espaciodatos import USER_AGENT, designacion

URL = "https://neo.ssa.esa.int/PSDB-portlet/download?file=esa_risk_list"
CODIFICACION = "utf-8"
# Las tres líneas de encabezado, normalizados los espacios: son el contrato de las columnas.
ENCABEZADO = [
    "Object | Diameter | VI Max | VIs |",
    "Num/des. Name | m | *=Y | Date/Time | IP max | PS max |TS | Vel km/s | Years | IP cum | PS cum |",
    "AAAAAAAAAAAA AAAAAAAAAAAAAAAA | NNNN | A | YYYY-MM-DD HH:MM | EEEEEEEE | NNN.NN | NN | NNN.NN | "
    "YYYY-YYYY | EEEEEEEE | NNN.NN |",
]
_ACTUALIZADO = re.compile(r"^Last Update: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) UTC$")
_ANIOS = re.compile(r"^(\d{4})-(\d{4})$")
TORINO_AUSENTE = ("n/a", "n/d")


class EsaInvalido(DatosInvalidos):
    """El archivo de la ESA no cumple el contrato medido."""


def _espacios(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _num(s: str, campo: str, donde: str) -> float:
    try:
        return float(s)
    except ValueError:
        raise EsaInvalido(f"{donde}: {campo} ilegible {s!r}") from None


def _fila(linea: str, donde: str) -> dict:
    p = [x.strip() for x in linea.split("|")]
    if len(p) != 12 or p[11] != "":
        raise EsaInvalido(f"{donde}: {len(p)} campos; cada fila medida trae 11 separadores y termina en '|'")
    obj, diam, est, fecha, ip, ps, ts, vel, anios, ip_cum, ps_cum, _ = p
    if est not in ("*", ""):
        raise EsaInvalido(f"{donde}: la marca de estimado es {est!r}; se esperaba '*' o vacío")
    if ts in TORINO_AUSENTE:
        torino = None
    elif ts.isdigit() and 0 <= int(ts) <= 10:
        torino = int(ts)
    else:
        raise EsaInvalido(f"{donde}: Torino {ts!r} no es 0-10, n/a ni n/d")
    try:
        vi_max = datetime.strptime(fecha, "%Y-%m-%d %H:%M")
    except ValueError:
        raise EsaInvalido(f"{donde}: fecha del VI máximo {fecha!r} ilegible") from None
    m = _ANIOS.match(anios)
    if not m or int(m.group(1)) > int(m.group(2)):
        raise EsaInvalido(f"{donde}: años {anios!r} no es AAAA-AAAA creciente")
    p_max, p_cum = _num(ip, "IP max", donde), _num(ip_cum, "IP cum", donde)
    if not (0 < p_max <= p_cum <= 1):
        raise EsaInvalido(f"{donde}: no se cumple 0 < IP max <= IP cum <= 1 ({p_max}, {p_cum})")
    d_m = _num(diam, "diámetro", donde)
    if d_m <= 0:
        raise EsaInvalido(f"{donde}: diámetro {d_m} m")
    return {
        "objeto": obj,
        "clave": designacion.clave(obj),
        "provisional": designacion.provisional(obj),
        "diametro_km": d_m / 1000,
        "diametro_estimado": est == "*",
        "vi_max": vi_max,
        "ip_max": p_max,
        "ps_max": _num(ps, "PS max", donde),
        "torino": torino,
        "torino_codigo": ts,
        "vel_kms": _num(vel, "velocidad", donde),
        "anio_desde": int(m.group(1)),
        "anio_hasta": int(m.group(2)),
        "ip_cum": p_cum,
        "ps_cum": _num(ps_cum, "PS cum", donde),
    }


def leer(ruta: Path) -> dict:
    """La lista: `actualizado` (UTC, de la primera línea) y `filas`, ordenadas por `ps_cum`."""
    ruta = Path(ruta)
    if not ruta.is_file():
        raise EsaInvalido(f"{ruta}: el archivo no está en el disco")
    lineas = ruta.read_text(encoding=CODIFICACION).split("\n")
    if not lineas or not lineas[0].strip():
        raise EsaInvalido(f"{ruta.name}: el archivo está vacío")
    m = _ACTUALIZADO.match(lineas[0].strip())
    if not m:
        raise EsaInvalido(f"{ruta.name}: la primera línea es {lineas[0][:60]!r}; se esperaba 'Last Update: … UTC'")
    encabezado = [_espacios(x) for x in lineas[1:4]]
    if encabezado != ENCABEZADO:
        raise EsaInvalido(f"{ruta.name}: el encabezado cambió: {encabezado!r}")
    filas = [_fila(x, f"{ruta.name} línea {i}") for i, x in enumerate(lineas[4:], start=5) if x.strip()]
    if not filas:
        raise EsaInvalido(f"{ruta.name}: la lista no trae filas")
    claves = [f["clave"] for f in filas]
    if len(set(claves)) != len(claves):
        raise EsaInvalido(f"{ruta.name}: hay objetos repetidos")
    filas.sort(key=lambda f: -f["ps_cum"])
    return {"actualizado_utc": datetime.strptime(m.group(1), "%Y-%m-%d %H:%M"), "filas": filas}


def resumen(lista: dict) -> dict:
    f = lista["filas"]
    return {
        "actualizado_utc": lista["actualizado_utc"],
        "filas": len(f),
        "diametro_medido": sum(not x["diametro_estimado"] for x in f),
        "torino": {c: sum(x["torino_codigo"] == c for x in f) for c in sorted({x["torino_codigo"] for x in f})},
        "anio_min": min(x["anio_desde"] for x in f),
        "anio_max": max(x["anio_hasta"] for x in f),
        "numerados": sum(x["clave"].isdigit() for x in f),
    }


def descargar(destino: Path) -> Path:
    """Baja la lista a `destino`. **Sale a la red.** Un cuerpo vacío no se escribe."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    cuerpo = red.pedir(URL, cabeceras={"User-Agent": USER_AGENT})
    if not cuerpo.strip():
        raise EsaInvalido(f"{URL}: la respuesta vino vacía")
    destino.write_bytes(cuerpo)
    return destino


def sello(ruta: Path, *, filas: Optional[int] = None) -> procedencia.Sello:
    actualizado = leer(ruta)["actualizado_utc"]
    fuente = f"ESA NEOCC lista de riesgo (Last Update {actualizado:%Y-%m-%d %H:%M} UTC)"
    return procedencia.sello(fuente, ruta=Path(ruta), url=URL, filas=filas)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m espaciodatos esa", description=__doc__.splitlines()[0])
    ap.add_argument("accion", choices=["bajar", "resumen"])
    ap.add_argument("ruta", type=Path)
    ap.add_argument("--limite", type=int, default=10)
    args = ap.parse_args(argv)
    if args.accion == "bajar":
        print(descargar(args.ruta))
        return 0
    lista = leer(args.ruta)
    r = resumen(lista)
    print(
        f"{r['filas']} objetos, actualizada {r['actualizado_utc']:%Y-%m-%d %H:%M} UTC, "
        f"impactos {r['anio_min']}-{r['anio_max']}"
    )
    print(f"  diámetro medido en {r['diametro_medido']} · Torino {r['torino']} · numerados {r['numerados']}")
    for f in lista["filas"][: args.limite]:
        print(f"  {f['clave']:<14} PS {f['ps_cum']:6.2f}  IP {f['ip_cum']:.2e}  {f['anio_desde']}-{f['anio_hasta']}")
    print(procedencia.como_linea(sello(args.ruta, filas=r["filas"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
