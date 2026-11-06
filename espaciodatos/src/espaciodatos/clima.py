"""Clima espacial de NOAA SWPC (`services.swpc.noaa.gov`): Kp, escalas G/R/S y alertas.

Abierto, sin token. NOAA es la fuente oficial de pronósticos (DONKI, de la NASA, se declara
"prototyping quality"). Medido el 2026-11-06 a las 16:32 UTC:

| Archivo | Bytes | Qué trae |
|---|---|---|
| `products/noaa-planetary-k-index-forecast.json` | 6.906 | 81 franjas de 3 h, 2026-10-30 a 2026-11-09 (*) |
| `products/noaa-scales.json` | 1.106 | Escalas R/S/G de ayer, hoy y el pronóstico de 3 días |
| `products/alerts.json` | 55.219 | 86 mensajes de los últimos 30 días (2026-10-08 a 2026-11-06) |

(*) 61 `observed`, 3 `estimated` y 17 `predicted`.

Las trampas, cada una con su número:

- **La tormenta empieza en Kp 4,67, no en 5**: NOAA rotula G1 desde el "5−" (4,67). En el
  archivo, 6 franjas tienen escala (G1 con Kp 4,67 ×3 y 5,0 ×2; G2 con 6,0): **un umbral
  `Kp >= 5` pierde 3 de las 6**. El lector calcula la escala con la convención de tercios
  (G1 desde 4,67, G2 desde 5,67, ... G5 desde 8,67) y **rechaza** si no coincide con la que
  rotula NOAA. Medido para G1 y para G2 en 6,0; el resto de los umbrales sigue la misma
  convención y no se vio todavía.
- **`"observed": "estimated"` no quiere decir pasado**: a las 16:32 UTC, las franjas de las
  18:00 y las 21:00 ya figuran como `estimated` (la de las 21:00 con G1). El campo se llama
  `observed` y tiene tres valores; el lector lo llama `tipo`.
- **El mismo Kp tiene tres nombres y tres formas**: `kp` en el pronóstico, `Kp` en el observado,
  y en el archivo de 1 minuto tres a la vez: `kp_index` (entero), `estimated_kp` (decimal) y
  `kp` (`"2P"`, la notación en tercios). **`kp_index` redondea la notación**: `"3M"` (2,67) trae
  `kp_index: 3`, `"1M"` (0,67) trae 1. Usarlo como Kp sobreestima. `kp_de_notacion()` convierte.
- **`time_tag` sin zona** (`"2026-10-30T00:00:00"`) en los Kp, y con `Z` en el viento solar: es
  UTC en los dos. Es el **comienzo** de una franja de 3 h.
- **En las escalas, la clave `"1"` no es mañana: es el pronóstico de hoy**, con la misma fecha
  que la `"0"` (lo observado hoy). `"-1"` es ayer, `"2"` y `"3"` los dos días siguientes. En el
  pronóstico, R y S no traen escala sino probabilidades (**como strings**: `"35"`), y G sí.
- **El `product_id` de una alerta no es su código**: `K04W` contra `WARK04` (el código está
  dentro del texto). Los mensajes mezclan `\\r\\n` y `\\n`, y vienen del más nuevo al más viejo.

Uso:

    python -m espaciodatos clima bajar datos/
    python -m espaciodatos clima resumen datos/
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional, Sequence

from uydatos import procedencia, red
from uydatos.errores import DatosInvalidos

from espaciodatos import USER_AGENT
from espaciodatos._jpl import ahora_utc

BASE = "https://services.swpc.noaa.gov"
URLS = {
    "kp": f"{BASE}/products/noaa-planetary-k-index-forecast.json",
    "escalas": f"{BASE}/products/noaa-scales.json",
    "alertas": f"{BASE}/products/alerts.json",
}
TIPOS = {"observed": "observado", "estimated": "estimado", "predicted": "pronosticado"}
# Los valores posibles de Kp: tercios de 0 a 9, redondeados a dos decimales como los manda NOAA.
KP_VALIDOS = {round(i / 3, 2) for i in range(28)}
# G desde el "−" de cada número entero: 5− (4,67) es G1, 6− (5,67) G2, 7− G3, 8− G4, 9− G5.
UMBRALES_G = [(8.67, 5), (7.67, 4), (6.67, 3), (5.67, 2), (4.67, 1)]
CLAVES_ESCALAS = {"-1", "0", "1", "2", "3"}
TEXTOS_ESCALA = {None, "none", "minor", "moderate", "strong", "severe", "extreme"}
FRANJA = timedelta(hours=3)


class ClimaInvalido(DatosInvalidos):
    """Un archivo de NOAA SWPC no cumple el contrato medido."""


def escala_g(kp: float) -> int:
    """La escala G de un Kp, con la convención de NOAA medida (G1 desde 4,67)."""
    for umbral, g in UMBRALES_G:
        if kp >= umbral - 1e-9:
            return g
    return 0


def kp_de_notacion(texto: str) -> float:
    """`"3M"` → 2,67; `"2Z"` → 2,0; `"2P"` → 2,33. La notación en tercios del archivo de 1 minuto."""
    m = re.fullmatch(r"([0-9])([MZP])", texto or "")
    if not m:
        raise ClimaInvalido(f'Kp {texto!r}: se esperaba un dígito y M, Z o P ("3M", "2Z", "2P")')
    base, signo = int(m.group(1)), m.group(2)
    valor = base + {"M": -1 / 3, "Z": 0.0, "P": 1 / 3}[signo]
    if not 0 <= valor <= 9:
        raise ClimaInvalido(f"Kp {texto!r} fuera de 0 a 9")
    return round(valor, 2)


def _cargar(ruta: Path) -> Any:
    p = Path(ruta)
    if not p.is_file():
        raise ClimaInvalido(f"{p}: el archivo no está en el disco")
    texto = p.read_text(encoding="utf-8")
    if not texto.strip():
        raise ClimaInvalido(f"{p.name}: el archivo está vacío")
    try:
        return json.loads(texto)
    except json.JSONDecodeError as e:
        raise ClimaInvalido(f"{p.name}: no es JSON ({e.msg})") from None


def _instante(texto: str, donde: str) -> datetime:
    try:
        return datetime.strptime(texto, "%Y-%m-%dT%H:%M:%S")
    except (TypeError, ValueError):
        raise ClimaInvalido(
            f"{donde}: time_tag {texto!r} ilegible; NOAA manda 2026-10-30T00:00:00 (UTC, sin zona)"
        ) from None


def leer_kp(ruta: Path) -> list[dict]:
    """Las franjas de 3 h del Kp (observado, estimado y pronosticado), en orden y sin huecos."""
    ruta = Path(ruta)
    d = _cargar(ruta)
    if not isinstance(d, list) or not d:
        raise ClimaInvalido(f"{ruta.name}: se esperaba una lista de franjas no vacía")
    out = []
    for i, x in enumerate(d):
        donde = f"{ruta.name} franja {i}"
        if not isinstance(x, dict) or set(x) != {"time_tag", "kp", "observed", "noaa_scale"}:
            raise ClimaInvalido(f"{donde}: claves {sorted(x) if isinstance(x, dict) else x!r}; cambió el formato")
        kp = x["kp"]
        if isinstance(kp, bool) or not isinstance(kp, (int, float)) or round(float(kp), 2) not in KP_VALIDOS:
            raise ClimaInvalido(f"{donde}: Kp {kp!r} no es un tercio entre 0 y 9")
        if x["observed"] not in TIPOS:
            raise ClimaInvalido(f"{donde}: tipo {x['observed']!r}; los medidos son {sorted(TIPOS)}")
        g = escala_g(float(kp))
        rotulo = x["noaa_scale"]
        if rotulo is not None and rotulo != f"G{g}":
            raise ClimaInvalido(f"{donde}: Kp {kp} rotulado {rotulo!r} por NOAA y la convención medida da G{g}")
        if rotulo is None and g > 0:
            raise ClimaInvalido(f"{donde}: Kp {kp} sin rótulo de NOAA y la convención medida da G{g}")
        inicio = _instante(x["time_tag"], donde)
        out.append(
            {
                "inicio_utc": inicio,
                "fin_utc": inicio + FRANJA,
                "kp": float(kp),
                "tipo": TIPOS[x["observed"]],
                "escala_g": g,
            }
        )
    for a, b in zip(out, out[1:]):
        if b["inicio_utc"] - a["inicio_utc"] != FRANJA:
            raise ClimaInvalido(
                f"{ruta.name}: entre {a['inicio_utc']} y {b['inicio_utc']} no hay 3 h: falta o sobra una franja"
            )
    orden = ["observado", "estimado", "pronosticado"]
    if [orden.index(f["tipo"]) for f in out] != sorted(orden.index(f["tipo"]) for f in out):
        raise ClimaInvalido(f"{ruta.name}: los tipos no van observado → estimado → pronosticado")
    return out


def _escala(e: dict, donde: str, *, prob: tuple[str, ...]) -> dict:
    esc, txt = e.get("Scale"), e.get("Text")
    if txt not in TEXTOS_ESCALA:
        raise ClimaInvalido(f"{donde}: texto de escala {txt!r} desconocido")
    if esc is not None and not (isinstance(esc, str) and esc.isdigit() and 0 <= int(esc) <= 5):
        raise ClimaInvalido(f"{donde}: escala {esc!r} no es 0-5")
    out: dict = {"escala": int(esc) if esc is not None else None, "texto": txt}
    for p in prob:
        v = e.get(p)
        if v is not None and not (isinstance(v, str) and v.isdigit() and 0 <= int(v) <= 100):
            raise ClimaInvalido(f"{donde}: probabilidad {p} {v!r} no es 0-100")
        out[p] = int(v) if v is not None else None
    return out


def leer_escalas(ruta: Path) -> dict:
    """Las escalas R (radio), S (radiación) y G (geomagnética): ayer, hoy observado, y el
    pronóstico de hoy y los dos días siguientes (la clave "1" de NOAA es **hoy**)."""
    ruta = Path(ruta)
    d = _cargar(ruta)
    if not isinstance(d, dict) or set(d) != CLAVES_ESCALAS:
        raise ClimaInvalido(
            f"{ruta.name}: claves {sorted(d) if isinstance(d, dict) else d!r}; se esperaban {sorted(CLAVES_ESCALAS)}"
        )
    dias = {}
    for k in sorted(CLAVES_ESCALAS, key=int):
        e, donde = d[k], f"{ruta.name} clave {k}"
        try:
            fecha = date.fromisoformat(e["DateStamp"])
        except (KeyError, TypeError, ValueError):
            raise ClimaInvalido(f"{donde}: DateStamp ilegible") from None
        dias[k] = {
            "fecha": fecha,
            "R": _escala(e["R"], f"{donde} R", prob=("MinorProb", "MajorProb")),
            "S": _escala(e["S"], f"{donde} S", prob=("Prob",)),
            "G": _escala(e["G"], f"{donde} G", prob=()),
        }
    if dias["1"]["fecha"] != dias["0"]["fecha"]:
        raise ClimaInvalido(
            f"{ruta.name}: la clave 1 es del {dias['1']['fecha']} y la 0 del {dias['0']['fecha']}; "
            "lo medido es que la 1 es el pronóstico del mismo día"
        )
    esperado = [dias["0"]["fecha"] + timedelta(days=n) for n in (0, 1, 2)]
    if [dias[k]["fecha"] for k in ("1", "2", "3")] != esperado or dias["-1"]["fecha"] != esperado[0] - timedelta(
        days=1
    ):
        raise ClimaInvalido(f"{ruta.name}: las fechas no son ayer, hoy y los dos días siguientes")
    return {"ayer": dias["-1"], "hoy": dias["0"], "pronostico": [dias["1"], dias["2"], dias["3"]]}


_CODIGO = re.compile(r"^Space Weather Message Code: ([A-Z0-9]{6})$", re.M)
_SERIE = re.compile(r"^Serial Number: (\d+)$", re.M)
TIPOS_ALERTA = {"ALT": "alerta", "WAR": "aviso", "WAT": "vigilancia", "SUM": "resumen"}


def leer_alertas(ruta: Path) -> list[dict]:
    """Los mensajes de los últimos 30 días, del más viejo al más nuevo, con el código del texto."""
    ruta = Path(ruta)
    d = _cargar(ruta)
    if not isinstance(d, list):
        raise ClimaInvalido(f"{ruta.name}: se esperaba una lista de mensajes")
    out = []
    for i, x in enumerate(d):
        donde = f"{ruta.name} mensaje {i}"
        if not isinstance(x, dict) or set(x) != {"product_id", "issue_datetime", "message"}:
            raise ClimaInvalido(f"{donde}: claves inesperadas")
        texto = x["message"].replace("\r\n", "\n")
        m, s = _CODIGO.search(texto), _SERIE.search(texto)
        if not m or not s:
            raise ClimaInvalido(f"{donde}: el texto no trae 'Space Weather Message Code' y 'Serial Number'")
        try:
            emitido = datetime.strptime(x["issue_datetime"], "%Y-%m-%d %H:%M:%S.%f")
        except (TypeError, ValueError):
            raise ClimaInvalido(f"{donde}: issue_datetime {x['issue_datetime']!r} ilegible") from None
        codigo = m.group(1)
        out.append(
            {
                "producto": x["product_id"],
                "codigo": codigo,
                "tipo": TIPOS_ALERTA.get(codigo[:3], "otro"),
                "serie": int(s.group(1)),
                "emitido_utc": emitido,
                "texto": texto,
                "titulo": next((ln.strip() for ln in texto.split("\n")[3:] if ln.strip()), ""),
            }
        )
    out.sort(key=lambda a: a["emitido_utc"])
    return out


def resumen(kp: list[dict], escalas: dict, alertas: list[dict], *, ahora: Optional[datetime] = None) -> dict:
    """Lo que hace falta para decidir: el Kp máximo de las últimas 24 h, las próximas franjas con
    tormenta, las escalas de hoy y los próximos días, y las alertas de las últimas 24 h."""
    ahora = ahora or ahora_utc()
    previas = [f for f in kp if ahora - timedelta(hours=24) <= f["inicio_utc"] <= ahora]
    proximas = [f for f in kp if f["escala_g"] > 0 and f["fin_utc"] > ahora]
    return {
        "kp_max_24h": max(previas, key=lambda f: f["kp"]) if previas else None,
        "proximas_tormentas": proximas,
        "escalas_hoy": escalas["hoy"],
        "pronostico": escalas["pronostico"],
        "alertas_24h": [a for a in alertas if a["emitido_utc"] >= ahora - timedelta(hours=24)],
    }


def descargar(carpeta: Path) -> dict[str, Path]:
    """Baja los tres archivos a `carpeta/clima_{kp,escalas,alertas}.json`. **Sale a la red.**"""
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    out = {}
    for nombre, url in URLS.items():
        cuerpo = red.pedir(url, cabeceras={"User-Agent": USER_AGENT})
        if not cuerpo.strip():
            raise ClimaInvalido(f"{url}: la respuesta vino vacía")
        p = carpeta / f"clima_{nombre}.json"
        p.write_bytes(cuerpo)
        out[nombre] = p
    return out


def sello(nombre: str, ruta: Path, *, filas: Optional[int] = None) -> procedencia.Sello:
    return procedencia.sello(f"NOAA SWPC {nombre}", ruta=Path(ruta), url=URLS[nombre], filas=filas)


def _linea_escalas(dia: dict) -> str:
    r, s, g = dia["R"], dia["S"], dia["G"]
    partes = [f"G{g['escala']}" if g["escala"] is not None else "G ?"]
    partes.append(f"R{r['escala']}" if r["escala"] is not None else f"R1-2 {r['MinorProb']}% · R3+ {r['MajorProb']}%")
    partes.append(f"S{s['escala']}" if s["escala"] is not None else f"S1+ {s['Prob']}%")
    return " · ".join(partes)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m espaciodatos clima", description=__doc__.splitlines()[0])
    ap.add_argument("accion", choices=["bajar", "resumen"])
    ap.add_argument("carpeta", type=Path)
    args = ap.parse_args(argv)
    if args.accion == "bajar":
        for p in descargar(args.carpeta).values():
            print(p)
        return 0
    c = args.carpeta
    kp, esc, al = (
        leer_kp(c / "clima_kp.json"),
        leer_escalas(c / "clima_escalas.json"),
        leer_alertas(c / "clima_alertas.json"),
    )
    r = resumen(kp, esc, al, ahora=ahora_utc())
    m = r["kp_max_24h"]
    if m:
        print(
            f"Kp máximo de las últimas 24 h: {m['kp']:.2f} "
            f"({m['inicio_utc']:%d/%m %H:%M} UTC, {m['tipo']}, G{m['escala_g']})"
        )
    print(f"Hoy ({esc['hoy']['fecha']}): {_linea_escalas(esc['hoy'])}")
    for d in esc["pronostico"]:
        print(f"  pronóstico {d['fecha']}: {_linea_escalas(d)}")
    for f in r["proximas_tormentas"]:
        print(
            f"  tormenta G{f['escala_g']} {f['inicio_utc']:%d/%m %H:%M}-{f['fin_utc']:%H:%M} UTC, "
            f"Kp {f['kp']:.2f} ({f['tipo']})"
        )
    print(f"{len(r['alertas_24h'])} mensajes en las últimas 24 h")
    for a in r["alertas_24h"]:
        print(f"  {a['emitido_utc']:%d/%m %H:%M} {a['codigo']} ({a['tipo']}): {a['titulo']}")
    for nombre, filas in (("kp", len(kp)), ("escalas", None), ("alertas", len(al))):
        print(procedencia.como_linea(sello(nombre, c / f"clima_{nombre}.json", filas=filas)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
