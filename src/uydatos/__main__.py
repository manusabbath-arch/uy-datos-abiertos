"""`python -m uydatos`: los subcomandos de todos los lectores en un solo lugar.

    python -m uydatos                 # la lista
    python -m uydatos inumet resumen datos/inumet_temp.csv temperatura
    python -m uydatos catalogo inia-precipitacion-temps-extremas-sg

`semanas` y `rut` no estan en la lista a proposito: son modulos de biblioteca, sin CLI propia.
"""

from __future__ import annotations

import sys
from typing import Optional, Sequence

from uydatos import (
    ancap,
    ancap_ventas,
    bcu,
    catalogo,
    compras,
    elecciones,
    hojas,
    ibge,
    ideuy,
    indec,
    inia,
    inumet,
    limites,
    mides,
    parlamento,
    red,
    salto_grande,
)

LECTORES = {
    "ancap": ancap,
    "ancap_ventas": ancap_ventas,
    "bcu": bcu,
    "catalogo": catalogo,
    "compras": compras,
    "elecciones": elecciones,
    "hojas": hojas,
    "ibge": ibge,
    "ideuy": ideuy,
    "indec": indec,
    "inia": inia,
    "inumet": inumet,
    "limites": limites,
    "mides": mides,
    "parlamento": parlamento,
    "red": red,
    "salto_grande": salto_grande,
}


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print("uydatos: lectores de datos publicos de Uruguay\n")
        print("  python -m uydatos <lector> [argumentos]\n")
        print("Lectores: " + ", ".join(sorted(LECTORES)))
        return 0
    lector, resto = argv[0], argv[1:]
    if lector not in LECTORES:
        print(f"lector {lector!r} no existe. Hay: {', '.join(sorted(LECTORES))}", file=sys.stderr)
        return 2
    return LECTORES[lector].main(resto)


if __name__ == "__main__":
    sys.exit(main())
