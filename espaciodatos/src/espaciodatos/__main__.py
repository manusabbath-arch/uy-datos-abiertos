"""`python -m espaciodatos <fuente> ...`: el comando de cada lector, y `todo` para bajar y cruzar.

python -m espaciodatos todo datos/        # baja las cinco fuentes y muestra el cruce
python -m espaciodatos cruce datos/       # sólo el cruce, sobre lo ya bajado
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Optional, Sequence

from uydatos import procedencia

from espaciodatos import _jpl, bolidos, cad, clima, cruce, esa, sentry, vigilancia

LECTORES = {"cad": cad, "sentry": sentry, "bolidos": bolidos, "esa": esa, "clima": clima}


def bajar_todo(carpeta: Path) -> dict[str, Path]:
    """Las cinco copias del mismo momento a `carpeta`. **Sale a la red.**"""
    carpeta = Path(carpeta)
    out = sentry.descargar(carpeta)
    out["esa_riesgo"] = esa.descargar(carpeta / "esa_riesgo.txt")
    out["bolidos"] = bolidos.descargar(carpeta / "bolidos.json")
    out["cad"] = cad.descargar(carpeta / "cad.json", date(1900, 1, 1), date(2200, 1, 1))
    return out


def imprimir_cruce(carpeta: Path, limite: int = 8) -> None:
    carpeta = Path(carpeta)
    jpl = sentry.leer(carpeta / "sentry.json")
    lista = esa.leer(carpeta / "esa_riesgo.txt")
    retirados = sentry.leer_retirados(carpeta / "sentry_retirados.json")
    c = cruce.comparar(jpl, lista, retirados)
    print(f"JPL {c['jpl']} · ESA {c['esa']} · en las dos {c['comunes']}")
    print(f"  el primero de JPL: {c['primero_jpl']} · el primero de la ESA: {c['primero_esa']}")
    print(f"  la ESA lista {len(c['esa_lista_lo_que_jpl_retiro'])} objetos que JPL retiró; los de mayor Palermo:")
    for x in c["esa_lista_lo_que_jpl_retiro"][:limite]:
        print(f"    {x['clave']:<12} PS ESA {x['ps_esa']:6.2f}  retirado por JPL el {x['retirado_jpl_utc']:%Y-%m-%d}")
    fuera = sum(x["fuera_del_horizonte_esa"] for x in c["solo_jpl"])
    print(f"  sólo en JPL {len(c['solo_jpl'])} ({fuera} fuera del horizonte de la ESA, {c['horizonte_esa']})")
    print(f"  Palermo distinto en más de {c['umbral_ps']:g} en {len(c['diferencias_ps'])} objetos; los mayores:")
    for x in c["diferencias_ps"][:limite]:
        print(f"    {x['clave']:<12} JPL {x['ps_jpl']:6.2f}  ESA {x['ps_esa']:6.2f}")
    print(procedencia.como_linea(sentry.sello(carpeta / "sentry.json", filas=c["jpl"])))
    print(procedencia.como_linea(esa.sello(carpeta / "esa_riesgo.txt", filas=c["esa"])))


def informe_vigilancia(antes: Path, despues: Path, *, dias: int = 30, max_ld: float = 5.0) -> str:
    """El informe de vigilancia entre dos carpetas bajadas con `todo`. No sale a la red.

    Los próximos acercamientos salen de `despues/cad.json` si está."""
    antes, despues = Path(antes), Path(despues)
    retirados = sentry.leer_retirados(despues / "sentry_retirados.json")
    jpl = vigilancia.comparar_sentry(
        sentry.leer(antes / "sentry.json"), sentry.leer(despues / "sentry.json"), retirados
    )
    lista = esa.leer(despues / "esa_riesgo.txt")
    e = vigilancia.comparar_esa(esa.leer(antes / "esa_riesgo.txt"), lista)
    c = cruce.comparar(sentry.leer(despues / "sentry.json"), lista, retirados)
    ahora = _jpl.ahora_utc()
    prox = None
    sellos = [
        procedencia.como_linea(sentry.sello(despues / "sentry.json")),
        procedencia.como_linea(esa.sello(despues / "esa_riesgo.txt")),
    ]
    if (despues / "cad.json").is_file():
        prox = cad.proximos(cad.leer(despues / "cad.json"), desde=ahora, dias=dias, max_ld=max_ld)
        sellos.append(procedencia.como_linea(cad.sello(despues / "cad.json")))
    return vigilancia.informe(
        jpl,
        e,
        retirados_jpl_que_esa_lista=c["esa_lista_lo_que_jpl_retiro"],
        proximos=prox,
        sellos=sellos,
        generado=ahora,
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in (*LECTORES, "cruce", "todo", "vigilar", "herramienta"):
        print(__doc__)
        print("fuentes: " + ", ".join([*LECTORES, "cruce", "todo", "vigilar", "herramienta"]))
        return 2
    fuente, resto = argv[0], argv[1:]
    if fuente == "herramienta":
        from espaciodatos import herramientas

        return herramientas.main(resto)
    if fuente == "vigilar":
        if len(resto) != 2:
            print("vigilar necesita dos carpetas: la copia anterior y la nueva")
            return 2
        print(informe_vigilancia(Path(resto[0]), Path(resto[1])), end="")
        return 0
    if fuente in LECTORES:
        return LECTORES[fuente].main(resto)
    if not resto:
        print(f"{fuente} necesita la carpeta")
        return 2
    if fuente == "todo":
        for nombre, p in bajar_todo(Path(resto[0])).items():
            print(f"{nombre:<18} {p}")
    imprimir_cruce(Path(resto[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
