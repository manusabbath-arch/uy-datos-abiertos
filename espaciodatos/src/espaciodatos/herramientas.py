"""Las preguntas que un agente le hace a estos datos, como funciones que devuelven JSON.

Pensado para que `mcp-uruguay` (u otro servidor MCP) las envuelva sin lógica propia: cada
herramienta lee **lo ya bajado** en una carpeta (no sale a la red; para eso está `actualizar`), y
devuelve siempre la misma forma:

    {"datos": ..., "advertencias": [...], "procedencia": [<sello>, ...]}

- `datos` es serializable con `json.dumps` tal cual: fechas en ISO 8601, sin objetos de Python.
- `advertencias` dice, en castellano y en la respuesta misma, lo que una cifra **no** es: que el
  diámetro de Sentry es estimado, que el instante de CAD es TDB, que un Torino nulo no es cero.
  Un agente que cite el número cita también la advertencia.
- `procedencia` son los sellos de `uydatos.procedencia` de cada archivo leído, con la versión del
  API y el sha256: de dónde salió cada número y de cuándo es la copia.

El registro `HERRAMIENTAS` trae el nombre, la descripción y los parámetros de cada una, para que el
servidor las publique sin repetir el texto.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Optional

from uydatos import procedencia

from espaciodatos import _jpl, bolidos, cad, clima, cruce, designacion, esa, sentry

AVISO_TDB = "Los instantes de acercamiento están en TDB, no en UTC (difieren ~69 s; al minuto da igual)."
AVISO_DIAMETRO = (
    "El diámetro de Sentry es una estimación desde la magnitud H con albedo supuesto de 0,154, no una "
    "medida; puede errar por un factor 2."
)
AVISO_TORINO = "Un Torino nulo no es 0: la escala no está definida para impactos a más de 100 años."
AVISO_PALERMO = "El Palermo es logarítmico: una diferencia de 1 es un factor 10 de riesgo."


def a_json(x: Any) -> Any:
    """Convierte fechas, Counter y tuplas a algo que `json.dumps` acepta, recursivamente."""
    if isinstance(x, (datetime, date)):
        return x.isoformat()
    if isinstance(x, Counter):
        return dict(x)
    if isinstance(x, dict):
        return {str(k): a_json(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [a_json(v) for v in x]
    return x


def _respuesta(datos: Any, advertencias: list[str], sellos: list[procedencia.Sello]) -> dict:
    return {"datos": a_json(datos), "advertencias": advertencias, "procedencia": [dict(s) for s in sellos]}


def _archivo(carpeta: Path, nombre: str) -> Path:
    p = Path(carpeta) / nombre
    if not p.is_file():
        raise FileNotFoundError(f"{p}: no está; correr `actualizar` (o `python -m espaciodatos todo {carpeta}`)")
    return p


def actualizar(carpeta: Path) -> dict:
    """Baja todas las fuentes a `carpeta`. **La única herramienta que sale a la red.**"""
    from espaciodatos.__main__ import bajar_todo

    rutas = bajar_todo(Path(carpeta))
    rutas.update({f"clima_{k}": v for k, v in clima.descargar(Path(carpeta)).items()})
    return _respuesta({k: str(v) for k, v in rutas.items()}, [], [])


def proximos_acercamientos(carpeta: Path, dias: int = 30, max_ld: float = 5.0) -> dict:
    """Los acercamientos a la Tierra de los próximos `dias` días a menos de `max_ld` distancias lunares."""
    ruta = _archivo(carpeta, "cad.json")
    filas = cad.proximos(cad.leer(ruta), desde=_jpl.ahora_utc(), dias=dias, max_ld=max_ld)
    datos = [
        {
            "objeto": f["nombre"],
            "des": f["des"],
            "instante_tdb": f["instante_tdb"],
            "incertidumbre_3sigma_min": f["t_sigma_min"],
            "incertidumbre_es_cota": f["t_sigma_es_cota"],
            "distancia_ld": round(f["dist_ld"], 3),
            "distancia_km": round(f["dist_km"]),
            "distancia_min_3sigma_km": round(f["dist_min_au"] * cad.KM_POR_AU),
            "velocidad_kms": round(f["v_rel_kms"], 2),
            "h": f["h"],
            "diametro_medido_km": f["diametro_km"],
        }
        for f in filas
    ]
    avisos = [AVISO_TDB]
    if any(f["diametro_km"] is None for f in filas):
        avisos.append("La mayoría de estos objetos no tiene diámetro medido: `diametro_medido_km` es nulo, no cero.")
    return _respuesta(datos, avisos, [cad.sello(ruta, filas=len(filas))])


def riesgo_de_impacto(carpeta: Path, limite: int = 10) -> dict:
    """Los objetos de mayor riesgo según JPL y según la ESA, cada lista con su orden."""
    rj, re_ = _archivo(carpeta, "sentry.json"), _archivo(carpeta, "esa_riesgo.txt")
    jpl, lista = sentry.leer(rj), esa.leer(re_)
    datos = {
        "jpl": [
            {
                "clave": f["clave"],
                "objeto": f["nombre"],
                "palermo_acumulado": f["ps_cum"],
                "probabilidad": f["ip"],
                "torino": f["torino"],
                "anios": [f["anio_desde"], f["anio_hasta"]],
                "diametro_estimado_km": f["diametro_estimado_km"],
            }
            for f in jpl[:limite]
        ],
        "esa": [
            {
                "clave": f["clave"],
                "palermo_acumulado": f["ps_cum"],
                "probabilidad": f["ip_cum"],
                "torino": f["torino"],
                "torino_codigo": f["torino_codigo"],
                "anios": [f["anio_desde"], f["anio_hasta"]],
                "diametro_km": f["diametro_km"],
                "diametro_es_estimado": f["diametro_estimado"],
            }
            for f in lista["filas"][:limite]
        ],
        "esa_actualizada_utc": lista["actualizado_utc"],
    }
    avisos = [
        AVISO_DIAMETRO,
        AVISO_TORINO,
        AVISO_PALERMO,
        "La lista de la ESA llega hasta ~2127; la de JPL, hasta 2880.",
    ]
    return _respuesta(datos, avisos, [sentry.sello(rj, filas=len(jpl)), esa.sello(re_, filas=len(lista["filas"]))])


def estado_de_un_objeto(carpeta: Path, objeto: str) -> dict:
    """Todo lo que las copias dicen de un objeto: si está en cada lista de riesgo, si JPL lo retiró
    y cuándo, y sus acercamientos futuros. Acepta `2008 JL3`, `2008JL3`, `99942`, `(2014 SC324)`."""
    clave = designacion.clave(objeto)
    rj, rr, re_, rc = (
        _archivo(carpeta, "sentry.json"),
        _archivo(carpeta, "sentry_retirados.json"),
        _archivo(carpeta, "esa_riesgo.txt"),
        _archivo(carpeta, "cad.json"),
    )
    jpl = {f["clave"]: f for f in sentry.leer(rj)}
    retirados = {r["clave"]: r for r in sentry.leer_retirados(rr)}
    lista = esa.leer(re_)
    en_esa = {f["clave"]: f for f in lista["filas"]}
    ahora = _jpl.ahora_utc()
    # El `des` de CAD ya está en la forma de JPL (y trae cometas, como 289P, que no tienen clave de asteroide)
    acercamientos = [f for f in cad.leer(rc) if f["des"] == clave and f["instante_tdb"] > ahora]
    j = jpl.get(clave)
    e = en_esa.get(clave)
    r = retirados.get(clave)
    datos = {
        "clave": clave,
        "jpl": None
        if j is None
        else {
            "palermo_acumulado": j["ps_cum"],
            "probabilidad": j["ip"],
            "torino": j["torino"],
            "anios": [j["anio_desde"], j["anio_hasta"]],
        },
        "jpl_retirado_utc": r["retirado_utc"] if r else None,
        "esa": None
        if e is None
        else {
            "palermo_acumulado": e["ps_cum"],
            "probabilidad": e["ip_cum"],
            "torino_codigo": e["torino_codigo"],
            "anios": [e["anio_desde"], e["anio_hasta"]],
        },
        "acercamientos_futuros": [
            {
                "instante_tdb": f["instante_tdb"],
                "distancia_ld": round(f["dist_ld"], 3),
                "dist_min_en_cero": f["dist_min_en_cero"],
            }
            for f in acercamientos
        ],
    }
    avisos = [AVISO_TDB]
    if r and e:
        avisos.append(
            f"JPL lo retiró el {r['retirado_utc']:%Y-%m-%d} (descartó todos sus impactos) y la ESA lo sigue listando: "
            "las agencias no coinciden."
        )
    if j is None and r is None and e is None:
        avisos.append("No figura en ninguna lista de riesgo ni entre los retirados de JPL.")
    if j and j["torino"] is None:
        avisos.append(AVISO_TORINO)
    sellos = [sentry.sello(rj), sentry.sello(rr), esa.sello(re_), cad.sello(rc)]
    return _respuesta(datos, avisos, sellos)


def desacuerdos_entre_agencias(carpeta: Path, limite: int = 10, umbral_palermo: float = 1.0) -> dict:
    """Dónde no coinciden JPL y la ESA: lo que una lista y la otra retiró, y los Palermo distintos."""
    rj, rr, re_ = (
        _archivo(carpeta, "sentry.json"),
        _archivo(carpeta, "sentry_retirados.json"),
        _archivo(carpeta, "esa_riesgo.txt"),
    )
    c = cruce.comparar(sentry.leer(rj), esa.leer(re_), sentry.leer_retirados(rr), umbral_ps=umbral_palermo)
    datos = {
        "jpl": c["jpl"],
        "esa": c["esa"],
        "en_las_dos": c["comunes"],
        "primero_jpl": c["primero_jpl"],
        "primero_esa": c["primero_esa"],
        "esa_lista_lo_que_jpl_retiro": {
            "total": len(c["esa_lista_lo_que_jpl_retiro"]),
            "mayores": c["esa_lista_lo_que_jpl_retiro"][:limite],
        },
        "palermo_distinto": {
            "total": len(c["diferencias_ps"]),
            "umbral": umbral_palermo,
            "mayores": c["diferencias_ps"][:limite],
        },
        "solo_jpl_fuera_del_horizonte_esa": [x["clave"] for x in c["solo_jpl"] if x["fuera_del_horizonte_esa"]],
    }
    avisos = [AVISO_PALERMO, "El cruce no dice quién tiene razón: dice dónde mirar, con la fecha de cada lista."]
    return _respuesta(datos, avisos, [sentry.sello(rj), sentry.sello(rr), esa.sello(re_)])


def bolidos_cerca(carpeta: Path, lat: float = -32.5, lon: float = -56.0, radio_km: float = 600.0) -> dict:
    """Los bólidos registrados a menos de `radio_km` de un punto (por defecto, el centro de Uruguay)."""
    ruta = _archivo(carpeta, "bolidos.json")
    filas = bolidos.leer(ruta)
    cerca = bolidos.cerca(filas, lat, lon, radio_km)
    datos = {
        "bolidos": [
            {
                "instante_utc": b["instante_utc"],
                "lat": b["lat"],
                "lon": b["lon"],
                "distancia_km": round(b["distancia_km"]),
                "energia_impacto_kt": b["energia_impacto_kt"],
                "altura_km": b["alt_km"],
                "velocidad_kms": b["vel_kms"],
            }
            for b in cerca
        ],
        "sin_ubicacion_en_el_archivo": sum(b["lat"] is None for b in filas),
    }
    avisos = ["Los bólidos sin ubicación no se cuentan como lejanos: se dejan afuera y se informa cuántos son."]
    return _respuesta(datos, avisos, [bolidos.sello(ruta, filas=len(filas))])


def clima_espacial(carpeta: Path) -> dict:
    """Kp de las últimas 24 h, próximas tormentas geomagnéticas, escalas G/R/S y alertas de NOAA."""
    rk, re_, ra = (
        _archivo(carpeta, "clima_kp.json"),
        _archivo(carpeta, "clima_escalas.json"),
        _archivo(carpeta, "clima_alertas.json"),
    )
    kp, escalas, alertas = clima.leer_kp(rk), clima.leer_escalas(re_), clima.leer_alertas(ra)
    r = clima.resumen(kp, escalas, alertas)
    datos = {
        "kp_max_24h": r["kp_max_24h"],
        "proximas_tormentas": r["proximas_tormentas"],
        "escalas_hoy": r["escalas_hoy"],
        "pronostico_3_dias": r["pronostico"],
        "alertas_24h": [{k: a[k] for k in ("emitido_utc", "codigo", "tipo", "titulo")} for a in r["alertas_24h"]],
    }
    avisos = [
        'La escala G empieza en Kp 4,67 ("5−"), no en 5.',
        "Una franja 'estimado' puede ser futura: no quiere decir observada.",
        "El primer día del pronóstico es hoy, no mañana.",
    ]
    sellos = [
        clima.sello("kp", rk, filas=len(kp)),
        clima.sello("escalas", re_),
        clima.sello("alertas", ra, filas=len(alertas)),
    ]
    return _respuesta(datos, avisos, sellos)


def _parametros(f: Callable) -> dict[str, str]:
    import inspect

    out = {}
    for n, p in inspect.signature(f).parameters.items():
        if n == "carpeta":
            continue
        out[n] = "requerido" if p.default is inspect.Parameter.empty else f"opcional, por defecto {p.default!r}"
    return out


_FUNCIONES = [
    proximos_acercamientos,
    riesgo_de_impacto,
    estado_de_un_objeto,
    desacuerdos_entre_agencias,
    bolidos_cerca,
    clima_espacial,
]
HERRAMIENTAS: dict[str, dict] = {
    f.__name__: {"funcion": f, "descripcion": (f.__doc__ or "").strip().split("\n\n")[0], "parametros": _parametros(f)}
    for f in _FUNCIONES
}


def llamar(nombre: str, carpeta: Path, **kwargs: Any) -> str:
    """Llama una herramienta por nombre y devuelve el JSON como texto (lo que un servidor MCP manda)."""
    if nombre not in HERRAMIENTAS:
        raise KeyError(f"{nombre!r} no es una herramienta; las que hay: {sorted(HERRAMIENTAS)}")
    return json.dumps(HERRAMIENTAS[nombre]["funcion"](Path(carpeta), **kwargs), ensure_ascii=False, indent=1)


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="python -m espaciodatos herramienta", description=__doc__.splitlines()[0])
    ap.add_argument("nombre", choices=sorted(HERRAMIENTAS))
    ap.add_argument("carpeta", type=Path)
    ap.add_argument("--param", action="append", default=[], help="nombre=valor; repetible")
    args = ap.parse_args(argv)
    kwargs: dict[str, Any] = {}
    for p in args.param:
        k, _, v = p.partition("=")
        try:
            kwargs[k] = json.loads(v)
        except json.JSONDecodeError:
            kwargs[k] = v
    print(llamar(args.nombre, args.carpeta, **kwargs))
    return 0
