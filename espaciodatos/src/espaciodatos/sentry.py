"""La lista de riesgo de impacto de JPL (Sentry, `sentry.api`): resumen, retirados y un objeto.

Abierto, sin token. Medido el 2026-11-06 (hora de Uruguay), versión `2.0`:

- **Resumen (modo S)**: 2.239 objetos, 586.463 bytes, sha256 `b7b9a4ad9406a71a…`. Impactos
  posibles de 2026 a **2880**.
- **Retirados (modo R)**: 3.596 objetos, de 2002-01-15 a hoy; **2 retirados el mismo día de la
  medición** y 20 en los últimos 30 días. La lista se mueve todos los días: una copia de ayer no
  es la lista de hoy.

Las trampas, cada una con su número:

- **El diámetro de Sentry es una estimación, no una medida**: viene en las 2.239 filas y la
  documentación dice que sale de `h` "suponiendo un albedo de 0,154". En CAD, de los 2.156
  objetos de Sentry que tienen acercamientos, **2.147 no tienen diámetro**. Donde los dos lo
  traen difieren hasta el doble (2015 XO129: 31 m en Sentry, 60 m en CAD). El campo se llama
  `diametro_estimado_km` para que no se lea como medido.
- **`ts_max` nulo no es cero**: 2 objetos (101955 Bennu y 29075 1950 DA), justamente los dos de
  mayor riesgo de la lista. La escala de Torino sólo está definida para impactos a menos de 100
  años, y los de ellos son de 2178-2290 y 2880. Se entrega `None` con `torino_definido = False`.
- **`last_obs` tiene un formato con día fraccionario** en 1 de 2.239 filas (Bennu:
  `"2020-10-3.80160"`). Un `date.fromisoformat` sobre esa columna rompe en el objeto más famoso.
- **`n_imp` es entero**, aunque la documentación lo muestra entre comillas (ver `_jpl`).
- **Un objeto retirado responde HTTP 200 con `"error"`** (Apophis: `"specified object removed"`,
  retirado el 2021-02-21 08:22:28; 2024 YR4: retirado el 2026-03-05 16:02:50). Uno que nunca
  estuvo responde `"specified object not found"`, y una designación mal escrita, HTTP 400.
- **La designación de un retirado es la que tenía al retirarse**: un objeto numerado después
  puede figurar con su provisional. Se busca también por la provisional.
- **`ps_cum >= ps_max`** se cumple en las 2.239 filas (la escala acumulada suma todos los
  impactos posibles): si no se cumple, se rechaza.
- **El orden no es por riesgo**: la documentación dice que se ordene por `id`. El lector ordena
  por `ps_cum` descendente.

Uso:

    python -m espaciodatos sentry bajar datos/
    python -m espaciodatos sentry resumen datos/sentry.json
    python -m espaciodatos sentry estado "2024 YR4"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional, Sequence

from uydatos import procedencia, red

from espaciodatos import _jpl, designacion
from espaciodatos._jpl import JplInvalido

URL = f"{_jpl.BASE}/sentry.api"
URL_RETIRADOS = f"{URL}?removed=1"
FUENTE = "NASA/JPL Sentry Data API"
VERSION = "2.0"
CLAVES = {
    "des",
    "diameter",
    "fullname",
    "h",
    "id",
    "ip",
    "last_obs",
    "last_obs_jd",
    "n_imp",
    "ps_cum",
    "ps_max",
    "range",
    "ts_max",
    "v_inf",
}
_LAST_OBS = re.compile(r"^(\d{4})-(\d{2})-(\d{1,2})(?:\.\d+)?$")
_RANGO = re.compile(r"^(\d{4})-(\d{4})$")


class SentryInvalido(JplInvalido):
    """La respuesta de Sentry no cumple el contrato medido."""


def ultima_observacion(texto: str, donde: str = "last_obs") -> date:
    """`"2013-01-12"` o `"2020-10-3.80160"` (día fraccionario, Bennu) como `date`."""
    m = _LAST_OBS.match(texto or "")
    if not m:
        raise SentryInvalido(f"{donde}: last_obs {texto!r} ilegible; formatos medidos 2013-01-12 y 2020-10-3.80160")
    a, mes, d = (int(x) for x in m.groups())
    try:
        return date(a, mes, d)
    except ValueError:
        raise SentryInvalido(f"{donde}: last_obs {texto!r} no es una fecha") from None


def _objeto(o: dict, donde: str) -> dict:
    faltan, sobran = CLAVES - set(o), set(o) - CLAVES
    if faltan or sobran:
        raise SentryInvalido(
            f"{donde}: claves distintas de las medidas; faltan {sorted(faltan)}, sobran {sorted(sobran)}"
        )
    n = _jpl.numero
    ip = n(o["ip"], "ip", donde)
    if not 0 < ip <= 1:
        raise SentryInvalido(f"{donde}: probabilidad de impacto {ip} fuera de (0, 1]")
    ps_cum, ps_max = n(o["ps_cum"], "ps_cum", donde), n(o["ps_max"], "ps_max", donde)
    if ps_cum < ps_max:
        raise SentryInvalido(f"{donde}: ps_cum {ps_cum} menor que ps_max {ps_max}; la acumulada no puede ser menor")
    m = _RANGO.match(o["range"] or "")
    if not m or int(m.group(1)) > int(m.group(2)):
        raise SentryInvalido(f"{donde}: range {o['range']!r} no es AAAA-AAAA creciente")
    ts = o["ts_max"]
    torino = None if ts is None else _jpl.entero(ts, "ts_max", donde)
    if torino is not None and not 0 <= torino <= 10:
        raise SentryInvalido(f"{donde}: Torino {torino} fuera de 0 a 10")
    return {
        "des": o["des"],
        "clave": designacion.clave(o["des"]),
        "nombre": o["fullname"].strip(),
        "id": o["id"],
        "ip": ip,
        "ps_cum": ps_cum,
        "ps_max": ps_max,
        "torino": torino,
        "torino_definido": torino is not None,
        "n_imp": _jpl.entero(o["n_imp"], "n_imp", donde),
        "anio_desde": int(m.group(1)),
        "anio_hasta": int(m.group(2)),
        "h": n(o["h"], "h", donde),
        "diametro_estimado_km": n(o["diameter"], "diameter", donde),
        "v_inf_kms": n(o["v_inf"], "v_inf", donde),
        "ultima_obs": ultima_observacion(o["last_obs"], donde),
        "ultima_obs_jd": n(o["last_obs_jd"], "last_obs_jd", donde),
    }


def leer(ruta: Path) -> list[dict]:
    """El resumen (modo S) de un archivo bajado, ordenado por `ps_cum` descendente. No sale a la red."""
    ruta = Path(ruta)
    d = _jpl.cargar(ruta)
    _jpl.firma(d, FUENTE, VERSION, ruta.name)
    datos = d.get("data")
    if not isinstance(datos, list):
        raise SentryInvalido(f"{ruta.name}: no trae data; ¿es el resumen (modo S) o un objeto (modo O)?")
    _jpl.cuenta(d, datos, ruta.name)
    filas = [_objeto(o, f"{ruta.name} fila {i}") for i, o in enumerate(datos)]
    claves = [f["clave"] for f in filas]
    if len(set(claves)) != len(claves):
        raise SentryInvalido(f"{ruta.name}: hay designaciones repetidas en la lista")
    filas.sort(key=lambda f: -f["ps_cum"])
    return filas


def leer_retirados(ruta: Path) -> list[dict]:
    """Los retirados (modo R): designación al momento de retirarse y el instante UTC."""
    ruta = Path(ruta)
    d = _jpl.cargar(ruta)
    _jpl.firma(d, FUENTE, VERSION, ruta.name)
    datos = d.get("data")
    if not isinstance(datos, list) or not datos:
        raise SentryInvalido(
            f"{ruta.name}: la lista de retirados vino vacía; la documentación dice que siempre trae datos"
        )
    _jpl.cuenta(d, datos, ruta.name)
    out = []
    for i, o in enumerate(datos):
        if set(o) != {"des", "removed"}:
            raise SentryInvalido(f"{ruta.name} fila {i}: claves {sorted(o)}; se esperaban des y removed")
        try:
            cuando = datetime.strptime(o["removed"], "%Y-%m-%d %H:%M:%S")
        except (TypeError, ValueError):
            raise SentryInvalido(f"{ruta.name} fila {i}: removed {o['removed']!r} ilegible") from None
        out.append({"des": o["des"], "clave": designacion.clave(o["des"]), "retirado_utc": cuando})
    return out


def estado_desde_respuesta(d: dict[str, Any], des: str) -> dict:
    """Lee una respuesta del modo O: `en_lista`, `retirado` (con fecha) o `nunca`. Un error que
    no es ninguno de los dos medidos se rechaza."""
    _jpl.firma(d, FUENTE, VERSION, des)
    error = d.get("error")
    if error == "specified object removed":
        return {"des": des, "estado": "retirado", "retirado_utc": datetime.strptime(d["removed"], "%Y-%m-%d %H:%M:%S")}
    if error == "specified object not found":
        return {"des": des, "estado": "nunca"}
    if error is not None:
        raise SentryInvalido(f"{des}: error {error!r} que no es ninguno de los medidos")
    resumen_o = d.get("summary")
    if not isinstance(resumen_o, dict):
        raise SentryInvalido(f"{des}: la respuesta no trae summary ni error")
    n = _jpl.numero
    ts = resumen_o.get("ts_max")
    return {
        "des": des,
        "estado": "en_lista",
        "ip": n(resumen_o.get("ip"), "ip", des),
        "ps_cum": n(resumen_o.get("ps_cum"), "ps_cum", des),
        "torino": None if ts is None else _jpl.entero(ts, "ts_max", des),
        "n_imp": _jpl.entero(resumen_o.get("n_imp"), "n_imp", des),
        "metodo": resumen_o.get("method"),
        "calculado_utc": resumen_o.get("cdate"),
        "publicado_utc": resumen_o.get("pdate"),
        "impactos_virtuales": len(d.get("data") or []),
    }


def estado(des: str) -> dict:
    """El estado de un objeto en Sentry. **Sale a la red.** Distingue retirado de nunca listado,
    que el API devuelve los dos con HTTP 200."""
    cuerpo = _jpl.pedir(f"{URL}?{red.codificar({'des': des})}")
    return estado_desde_respuesta(json.loads(cuerpo.decode("utf-8")), des)


def descargar(carpeta: Path) -> dict[str, Path]:
    """Baja el resumen y los retirados a `carpeta/sentry.json` y `carpeta/sentry_retirados.json`."""
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    out = {}
    for nombre, u in (("sentry", URL), ("sentry_retirados", URL_RETIRADOS)):
        p = carpeta / f"{nombre}.json"
        p.write_bytes(_jpl.pedir(u))
        out[nombre] = p
    return out


def sello(ruta: Path, *, filas: Optional[int] = None) -> procedencia.Sello:
    version = _jpl.firma(_jpl.cargar(ruta), FUENTE, VERSION, Path(ruta).name)
    return procedencia.sello(f"JPL Sentry {version}", ruta=Path(ruta), url=URL, filas=filas)


def _texto(f: dict) -> str:
    ts = f["torino"] if f["torino_definido"] else "n/d (>100 años)"
    return (
        f"{f['nombre']:<28} PS {f['ps_cum']:6.2f}  IP {f['ip']:.2e}  Torino {ts}  "
        f"{f['anio_desde']}-{f['anio_hasta']}  ~{f['diametro_estimado_km'] * 1000:.0f} m (estimado)"
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m espaciodatos sentry", description=__doc__.splitlines()[0])
    ap.add_argument("accion", choices=["bajar", "resumen", "estado"])
    ap.add_argument("ruta", help="carpeta (bajar), archivo (resumen) o designación (estado)")
    ap.add_argument("--limite", type=int, default=10)
    args = ap.parse_args(argv)
    if args.accion == "bajar":
        for p in descargar(Path(args.ruta)).values():
            print(p)
        return 0
    if args.accion == "estado":
        print(estado(args.ruta))
        return 0
    filas = leer(Path(args.ruta))
    print(f"{len(filas)} objetos en la lista de riesgo; los {args.limite} de mayor Palermo acumulado:")
    for f in filas[: args.limite]:
        print("  " + _texto(f))
    print(procedencia.como_linea(sello(Path(args.ruta), filas=len(filas))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
