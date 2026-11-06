"""Qué cambió entre dos copias de las listas de riesgo: la vigilancia.

Una lista de riesgo es una foto. Lo que interesa a quien vigila es **qué se movió**: un objeto
nuevo, uno que salió (y si JPL lo retiró), una probabilidad que subió, un Torino que dejó de ser 0.
Medido el 2026-11-06 con dos copias tomadas a **31 minutos** de distancia (15:59 y 16:30 UTC):

- Las tres copias cambiaron de sha256 (Sentry, retirados de Sentry y la ESA), y la ESA pasó de
  `Last Update 14:58` a `15:33 UTC`. **Un sha256 distinto no dice qué cambió**: en Sentry, los
  2.239 objetos son los mismos y cambiaron **2**.
- **2026 VX1 se movió en direcciones opuestas**: en JPL el Palermo subió de −7,27 a −7,05 (la
  probabilidad pasó de 2,7e-6 a 6,0e-6, con 18 → 11 impactos virtuales); en la ESA bajó de −6,72
  a **−9,09**. Media hora, el mismo objeto, una agencia más preocupada y la otra menos.
- La ESA sumó **2026 VF2** y cambió 14 objetos, todos descubiertos en octubre-noviembre de 2026:
  los recién descubiertos son los que se mueven.
- **2026 VC3**: JPL lo retiró a las 15:29:58 UTC; la ESA lo actualizó a las 15:33 y lo sigue listando.

Las reglas: una copia de la ESA **más vieja** que la anterior se rechaza (no se compara al revés);
un cambio se informa con los dos valores, nunca sólo el nuevo.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from uydatos.errores import DatosInvalidos

# Lo que se compara de cada objeto. `ultima_obs` es la señal de que hubo observaciones nuevas.
CAMPOS_SENTRY = ("ps_cum", "ps_max", "ip", "torino", "n_imp", "ultima_obs", "anio_desde", "anio_hasta")
CAMPOS_ESA = ("ps_cum", "ps_max", "ip_cum", "torino_codigo", "anio_desde", "anio_hasta", "vi_max")


class VigilanciaInvalida(DatosInvalidos):
    """Las dos copias no se pueden comparar."""


def _comparar(antes: list[dict], despues: list[dict], campos: tuple[str, ...]) -> dict:
    a = {f["clave"]: f for f in antes}
    d = {f["clave"]: f for f in despues}
    cambios = []
    for k in sorted(a.keys() & d.keys()):
        dif = {c: (a[k][c], d[k][c]) for c in campos if a[k][c] != d[k][c]}
        if dif:
            delta = d[k]["ps_cum"] - a[k]["ps_cum"]
            cambios.append({"clave": k, "campos": dif, "delta_ps": delta})
    cambios.sort(key=lambda x: -abs(x["delta_ps"]))
    return {
        "antes": len(a),
        "despues": len(d),
        "nuevos": [d[k] for k in sorted(d.keys() - a.keys(), key=lambda k: -d[k]["ps_cum"])],
        "salieron": [a[k] for k in sorted(a.keys() - d.keys(), key=lambda k: -a[k]["ps_cum"])],
        "cambios": cambios,
    }


def comparar_sentry(antes: list[dict], despues: list[dict], retirados: Optional[list[dict]] = None) -> dict:
    """Compara dos `sentry.leer()`. Con `sentry.leer_retirados()` de la copia nueva, cada objeto que
    salió dice si JPL lo retiró y cuándo; si no figura en los retirados, se dice también."""
    r = _comparar(antes, despues, CAMPOS_SENTRY)
    por_clave = {x["clave"]: x for x in (retirados or [])}
    r["salieron"] = [
        {
            "clave": f["clave"],
            "ps_cum": f["ps_cum"],
            "retirado_utc": por_clave[f["clave"]]["retirado_utc"] if f["clave"] in por_clave else None,
            "en_retirados": f["clave"] in por_clave if retirados is not None else None,
        }
        for f in r["salieron"]
    ]
    r["torino_cambio"] = [c for c in r["cambios"] if "torino" in c["campos"]]
    return r


def comparar_esa(antes: dict, despues: dict) -> dict:
    """Compara dos `esa.leer()`. Rechaza si la copia `despues` es más vieja que `antes`."""
    ta, td = antes["actualizado_utc"], despues["actualizado_utc"]
    if td < ta:
        raise VigilanciaInvalida(
            f"la copia 'despues' es de {td:%Y-%m-%d %H:%M} UTC y la 'antes' de {ta:%Y-%m-%d %H:%M}: "
            "están al revés, y comparar al revés convierte las altas en bajas"
        )
    r = _comparar(antes["filas"], despues["filas"], CAMPOS_ESA)
    r["antes_utc"], r["despues_utc"] = ta, td
    r["torino_cambio"] = [c for c in r["cambios"] if "torino_codigo" in c["campos"]]
    return r


def opuestos(jpl: dict, esa: dict, *, minimo: float = 0.1) -> list[dict]:
    """Objetos que cambiaron en las dos agencias en direcciones opuestas (una sube el riesgo, la otra
    lo baja), cada una por más de `minimo` en el Palermo acumulado."""
    dj = {c["clave"]: c["delta_ps"] for c in jpl["cambios"]}
    out = []
    for c in esa["cambios"]:
        k, de = c["clave"], c["delta_ps"]
        if k in dj and abs(dj[k]) > minimo and abs(de) > minimo and (dj[k] > 0) != (de > 0):
            out.append({"clave": k, "delta_ps_jpl": dj[k], "delta_ps_esa": de})
    return sorted(out, key=lambda x: -abs(x["delta_ps_jpl"] - x["delta_ps_esa"]))


def numero_es(x: float, decimales: int = 2, *, signo: bool = False) -> str:
    """`1594620.3` → `1.594.620`; `-6.72` → `-6,72`: miles con punto y decimales con coma, sin
    mezclar las dos convenciones en la misma tabla."""
    t = f"{x:{'+' if signo else ''},.{decimales}f}"
    return t.replace(",", "_").replace(".", ",").replace("_", ".")


def _ps(x: float) -> str:
    return numero_es(x)


def informe(
    jpl: dict,
    esa_cmp: dict,
    *,
    retirados_jpl_que_esa_lista: Optional[list[dict]] = None,
    proximos: Optional[list[dict]] = None,
    sellos: Optional[list[str]] = None,
    generado: Optional[datetime] = None,
    limite: int = 10,
) -> str:
    """El informe de vigilancia en Markdown. Toda cifra va con el antes y el después."""
    out = ["# Vigilancia de objetos cercanos"]
    if generado:
        out.append(f"\nGenerado {generado:%Y-%m-%d %H:%M} UTC.")
    out.append("\n## JPL Sentry\n")
    out.append(f"- Objetos: {jpl['antes']} → {jpl['despues']}")
    out.append(f"- Nuevos: {len(jpl['nuevos'])} · salieron: {len(jpl['salieron'])} · cambiaron: {len(jpl['cambios'])}")
    for f in jpl["nuevos"][:limite]:
        out.append(
            f"  - **Nuevo** {f['clave']}: Palermo {_ps(f['ps_cum'])}, impactos {f['anio_desde']}-{f['anio_hasta']}"
        )
    for f in jpl["salieron"][:limite]:
        cuando = f"retirado {f['retirado_utc']:%Y-%m-%d %H:%M} UTC" if f["retirado_utc"] else "sin figurar en retirados"
        out.append(f"  - **Salió** {f['clave']} ({cuando})")
    for c in jpl["torino_cambio"]:
        a, d = c["campos"]["torino"]
        out.append(f"  - **Torino** {c['clave']}: {a} → {d}")
    out.append("\n## ESA NEOCC\n")
    out.append(
        f"- Lista del {esa_cmp['antes_utc']:%Y-%m-%d %H:%M} → {esa_cmp['despues_utc']:%Y-%m-%d %H:%M} UTC: "
        f"{esa_cmp['antes']} → {esa_cmp['despues']} objetos"
    )
    out.append(
        f"- Nuevos: {len(esa_cmp['nuevos'])} · salieron: {len(esa_cmp['salieron'])} · "
        f"cambiaron: {len(esa_cmp['cambios'])}"
    )
    for f in esa_cmp["nuevos"][:limite]:
        out.append(
            f"  - **Nuevo** {f['clave']}: Palermo {_ps(f['ps_cum'])}, impactos {f['anio_desde']}-{f['anio_hasta']}"
        )
    for f in esa_cmp["salieron"][:limite]:
        out.append(f"  - **Salió** {f['clave']}")
    op = opuestos(jpl, esa_cmp)
    out.append("\n## Los cambios más grandes del Palermo\n")
    out.append("| Objeto | Agencia | Antes | Después |\n|---|---|---|---|")
    filas = [("JPL", c) for c in jpl["cambios"]] + [("ESA", c) for c in esa_cmp["cambios"]]
    filas.sort(key=lambda x: -abs(x[1]["delta_ps"]))
    for ag, c in filas[:limite]:
        a, d = c["campos"].get("ps_cum", (None, None))
        if a is None:
            continue
        out.append(f"| {c['clave']} | {ag} | {_ps(a)} | {_ps(d)} |")
    if op:
        out.append("\n## Las agencias se movieron en direcciones opuestas\n")
        for x in op:
            out.append(
                f"- **{x['clave']}**: el Palermo cambió {numero_es(x['delta_ps_jpl'], signo=True)} en JPL "
                f"y {numero_es(x['delta_ps_esa'], signo=True)} en la ESA"
            )
    if retirados_jpl_que_esa_lista:
        out.append(f"\n## La ESA lista {len(retirados_jpl_que_esa_lista)} objetos que JPL retiró\n")
        for x in retirados_jpl_que_esa_lista[:limite]:
            out.append(
                f"- {x['clave']}: Palermo ESA {_ps(x['ps_esa'])}, retirado por JPL el {x['retirado_jpl_utc']:%Y-%m-%d}"
            )
    if proximos:
        out.append("\n## Próximos acercamientos a menos de 5 distancias lunares\n")
        out.append("| Fecha (TDB) | Objeto | Distancia | ±3σ del instante | Velocidad |\n|---|---|---|---|---|")
        for f in proximos[:limite]:
            sigma = f"< {f['t_sigma_min']} min" if f["t_sigma_es_cota"] else f"{f['t_sigma_min']} min"
            out.append(
                f"| {f['instante_tdb']:%Y-%m-%d %H:%M} | {f['nombre']} | {numero_es(f['dist_ld'])} LD "
                f"({numero_es(f['dist_km'], 0)} km) | {sigma} | {numero_es(f['v_rel_kms'], 1)} km/s |"
            )
    if sellos:
        out.append("\n## Procedencia\n")
        out.extend(f"- {s}" for s in sellos)
    return "\n".join(out) + "\n"
