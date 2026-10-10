"""IPC nacional de Argentina (INDEC), desde la API de series de tiempo de datos.gob.ar.

La serie viva es el IPC Nacional base diciembre 2016 = 100, publicado desde 2017.

Las trampas, y por qué el lector las corta
-----------------------------------------
1. **La API sirve series muertas sin avisar.** Las bases 2003 y 2008 se discontinuaron en 2013
   y la API **las sigue devolviendo**. Pedir el id viejo no da error: da un índice que, leído
   como actual, miente. El id vivo es una constante (`ID_NACIONAL_VIVA`) y los de base vieja se
   rechazan por nombre.
2. **GBA no es el país.** La serie de Gran Buenos Aires (`ID_GBA`) es otra serie, con otra
   granularidad; confundirlas no es un error de redondeo.
3. **La API responde 403 al `User-Agent` por defecto de Python** y 200 a cualquier otro.
   `descargar()` manda el del paquete.

Y una que el lector se **niega** a hacer: **un índice no es una inflación.** Devuelve el valor
del índice; convertirlo a inflación mensual es una decisión del análisis, no una lectura.

Uso:
    python -m uydatos.indec bajar ipc.json
    python -m uydatos.indec leer ipc.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional, Sequence, Union

from uydatos import red

ID_NACIONAL_VIVA = "148.3_INIVELNAL_DICI_M_26"
ID_GBA = "148.3_INIVELGBADICI_M_26"

URL = "https://apis.datos.gob.ar/series/api/series/"
BASES_MUERTAS = ("DICI_M_48", "DICI_M_03", "DICI_M_38")


class IpcInvalido(ValueError):
    """El archivo no cumple el contrato de la fuente."""


def _validar_id(id_serie: str) -> None:
    if id_serie in (ID_NACIONAL_VIVA, ID_GBA):
        return
    if any(muerta in id_serie for muerta in BASES_MUERTAS):
        raise IpcInvalido(
            f"{id_serie}: es una serie de base vieja, discontinuada en 2013. La API la sigue "
            f"sirviendo y leerla como actual miente. Usar {ID_NACIONAL_VIVA}."
        )
    raise IpcInvalido(f"{id_serie}: id desconocido. Los ids declarados son {ID_NACIONAL_VIVA} y {ID_GBA}.")


def _url(id_serie: str) -> str:
    _validar_id(id_serie)
    return f"{URL}?ids={id_serie}&format=json&limit=1000"


def _pedido(id_serie: str = ID_NACIONAL_VIVA):
    """El pedido armado de la serie. Los tests miran su `User-Agent`; `descargar()` sale por `red.bajar()`."""
    return red.pedido(_url(id_serie))


def descargar(destino: Path, id_serie: str = ID_NACIONAL_VIVA) -> Path:
    """Baja la serie de la API a `destino`. **Única función que sale a la red.**"""
    return red.bajar(_url(id_serie), destino)


def leer(ruta: Path, id_serie: str = ID_NACIONAL_VIVA, solo_meta: bool = False) -> Union[list[dict], dict[str, Any]]:
    """Lee una respuesta guardada de la API. Rechaza en vez de arreglar.

    Con `solo_meta=True` devuelve un dict con `frecuencia`, `fuente`, `titulo`, `desde`, `hasta`
    y `n`. Si no, la lista de puntos `{"periodo": "AAAA-MM", "valor": float}`.

    **No devuelve inflación.** El índice no es la inflación.
    """
    _validar_id(id_serie)
    ruta = Path(ruta)
    if not ruta.is_file():
        raise IpcInvalido(f"{ruta}: el archivo no está en el disco")
    try:
        crudo = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise IpcInvalido(f"{ruta}: JSON ilegible ({e})") from None

    meta = crudo.get("meta") or []
    if not meta:
        raise IpcInvalido(f"{ruta}: sin bloque `meta`")
    cabecera = meta[0]
    detalle = meta[1] if len(meta) > 1 else {}
    if detalle.get("field", {}).get("id") not in (None, id_serie):
        raise IpcInvalido(f"{ruta}: el archivo es de la serie {detalle['field']['id']}, se pidió {id_serie}")
    dataset = detalle.get("dataset", {})
    info = {
        "frecuencia": cabecera.get("frequency"),
        "fuente": dataset.get("source", ""),
        "titulo": dataset.get("title", ""),
        "desde": cabecera.get("start_date", ""),
        "hasta": cabecera.get("end_date", ""),
        "n": crudo.get("count", 0),
    }
    if solo_meta:
        return info

    puntos = crudo.get("data") or []
    if not puntos:
        raise IpcInvalido(f"{ruta}: sin datos (`data` vacío)")
    serie = []
    for periodo, valor in puntos:
        if valor is None:
            continue
        serie.append({"periodo": str(periodo)[:7], "valor": float(valor)})
    if not serie:
        raise IpcInvalido(f"{ruta}: ninguna fila con valor")
    return serie


def factor(serie: list[dict], periodo: str, base: str) -> Optional[float]:
    """Cociente índice(`periodo`) / índice(`base`). `None` si falta alguno de los dos.

    Devuelve el **factor**, no el monto: para llevar pesos de `periodo` a pesos de `base`,
    dividir el monto por este factor.
    """
    valores = {f["periodo"]: f["valor"] for f in serie}
    if periodo not in valores or base not in valores or valores[base] == 0:
        return None
    return valores[periodo] / valores[base]


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m uydatos.indec", description=__doc__.splitlines()[0])
    ap.add_argument("orden", choices=["bajar", "leer"])
    ap.add_argument("archivo", type=Path)
    args = ap.parse_args(argv)
    if args.orden == "bajar":
        print(f"bajado {descargar(args.archivo)}")
        return 0
    serie = leer(args.archivo)
    info = leer(args.archivo, solo_meta=True)
    assert isinstance(serie, list) and isinstance(info, dict)
    print(f"{info['titulo']} | fuente: {info['fuente']} | frecuencia: {info['frecuencia']}")
    print(f"{len(serie)} puntos, {serie[0]['periodo']} a {serie[-1]['periodo']}")
    for f in serie[-3:]:
        print(f"  {f['periodo']}: {f['valor']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
