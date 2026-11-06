"""Dónde no coinciden la lista de riesgo de JPL (Sentry) y la de la ESA (NEOCC).

Las dos agencias calculan el riesgo de impacto por separado, con sus propias observaciones y
métodos. Que coincidan es lo esperable; **donde no coinciden está la información**, y ningún
consumidor de una sola lista lo ve. Medido el 2026-11-06 con las dos copias del mismo día:

- JPL lista **2.239** objetos, la ESA **2.205**; están en las dos **1.974**.
- **175 objetos que la ESA todavía lista fueron retirados por JPL**, algunos hace años: 2016 JT38
  el 2020-04-22, 2014 ML67 el 2021-08-09 (PS −3,81 en la ESA), 2023 XJ2 el 2024-07-09 (PS −5,37).
  Retirado quiere decir que JPL descartó todos los impactos posibles con más observaciones.
- **56 objetos están sólo en la ESA** sin haber sido retirados por JPL, y **265 sólo en JPL**.
  De éstos, sólo 2 están fuera del horizonte de la ESA (Bennu 2178-2290 y 1950 DA 2880); los otros
  263 están dentro, como 367943 Duende (2116-2122), y la ESA no los lista.
- En los 1.974 comunes, el Palermo acumulado difiere **más de 1 (un factor 10 de riesgo) en 292**
  y más de 2 en 89. La mayor diferencia: 2010 VQ, −9,21 en la ESA contra −4,41 en JPL.
- **El primero de cada lista es otro objeto**: 1950 DA en JPL (fuera del horizonte de la ESA) y
  2008 JL3 en la ESA (tercero en JPL).

El cruce no decide quién tiene razón: dice dónde mirar, con la fecha de cada lista.
"""

from __future__ import annotations

from typing import Optional

from espaciodatos import designacion


def comparar(
    jpl: list[dict],
    esa: dict,
    retirados_jpl: Optional[list[dict]] = None,
    *,
    umbral_ps: float = 1.0,
) -> dict:
    """Compara `sentry.leer()` contra `esa.leer()`, con `sentry.leer_retirados()` si se tiene.

    Un objeto que una agencia numeró y la otra no se empareja por la provisional del nombre."""
    por_jpl = {f["clave"]: f for f in jpl}
    # Numerados de JPL alcanzables también por su provisional ("443104 (2013 XK22)")
    alias = {}
    for f in jpl:
        p = designacion.provisional(f["nombre"])
        if p and p != f["clave"]:
            alias[p] = f["clave"]
    por_esa = {}
    for f in esa["filas"]:
        k = f["clave"]
        if k not in por_jpl and f["provisional"] in alias:
            k = alias[f["provisional"]]
        if k not in por_jpl and k in alias:
            k = alias[k]
        por_esa[k] = f
    retirados = {r["clave"]: r for r in (retirados_jpl or [])}

    comunes = sorted(por_jpl.keys() & por_esa.keys())
    solo_esa = sorted(por_esa.keys() - por_jpl.keys())
    solo_jpl = sorted(por_jpl.keys() - por_esa.keys())
    horizonte_esa = max(f["anio_hasta"] for f in esa["filas"])

    diferencias = []
    for k in comunes:
        a, b = por_jpl[k], por_esa[k]
        d = b["ps_cum"] - a["ps_cum"]
        if abs(d) > umbral_ps:
            diferencias.append({"clave": k, "ps_jpl": a["ps_cum"], "ps_esa": b["ps_cum"], "diferencia": d})
    diferencias.sort(key=lambda x: -abs(x["diferencia"]))

    esa_retirado_por_jpl = [
        {"clave": k, "retirado_jpl_utc": retirados[k]["retirado_utc"], "ps_esa": por_esa[k]["ps_cum"]}
        for k in solo_esa
        if k in retirados
    ]
    esa_retirado_por_jpl.sort(key=lambda x: -x["ps_esa"])
    return {
        "esa_actualizado_utc": esa["actualizado_utc"],
        "jpl": len(por_jpl),
        "esa": len(por_esa),
        "comunes": len(comunes),
        "solo_jpl": [
            {
                "clave": k,
                "ps_jpl": por_jpl[k]["ps_cum"],
                "fuera_del_horizonte_esa": por_jpl[k]["anio_desde"] > horizonte_esa,
            }
            for k in sorted(solo_jpl, key=lambda k: -por_jpl[k]["ps_cum"])
        ],
        "solo_esa": [
            {"clave": k, "ps_esa": por_esa[k]["ps_cum"], "retirado_por_jpl": k in retirados}
            for k in sorted(solo_esa, key=lambda k: -por_esa[k]["ps_cum"])
        ],
        "esa_lista_lo_que_jpl_retiro": esa_retirado_por_jpl,
        "diferencias_ps": diferencias,
        "umbral_ps": umbral_ps,
        "horizonte_esa": horizonte_esa,
        "primero_jpl": max(jpl, key=lambda f: f["ps_cum"])["clave"],
        "primero_esa": max(por_esa.items(), key=lambda kv: kv[1]["ps_cum"])[0],
    }
