"""Hojas de cálculo: leer un XLSX o un XLS por la firma del archivo, no por su extensión.

Medido el 10/10/26 sobre el catálogo de datos abiertos:

- **2.162 datasets** declaran algún recurso XLSX y **60** declaran `XLS`.
- **El `formato` que declara el catálogo no es confiable.** De 24 recursos declarados `XLS`, **23 son
  en realidad XLSX**: el recurso se llama `.xlsx` y su contenido es el ZIP de OOXML. El único `.xls`
  OLE de verdad de la muestra es el de AGESIC (`diccionario_eutic_2010.xls`). Por eso el motor sale
  de **la firma del archivo** —los primeros bytes— y no del metadato que alguien escribió.
- openpyxl **también se fía de la extensión**: con una ruta rechaza con `InvalidFileException` un
  XLSX que se llame `.xls`. Acá se le pasa el archivo abierto, que no tiene nombre que mirar.
- El XLSX de un indicador de MIDES trae **dos hojas**: `Datos` —la misma tabla que su CSV, pero con
  los números ya tipados— y `Metadatos` (`nombreDeAtributo`, `descripcion`, `tipoDeDato`). O sea que
  el XLSX declara el tipo de cada columna, cosa que el CSV no hace.
- **openpyxl en modo `read_only` miente con las dimensiones**: si la hoja no trae la dimensión
  declarada, `max_row` y `max_column` devuelven 1. Acá se lee entero, sin `read_only`.
- Los `.xls` de la Encuesta Continua de Hogares **no se pueden bajar**: viven en el sitio viejo del
  INE (`ine.gub.uy/c/document_library/...`) con la cadena de certificado rota
  (`CERTIFICATE_VERIFY_FAILED`). Eso es de la fuente, no de este lector.

Las dependencias son **opcionales**: el paquete base no engorda por leer una planilla. Con `pip
install uydatos[hojas]` se instalan las dos, y si falta la que hace falta, el error dice cuál.

Uso:
    python -m uydatos hojas ver datos/planilla.xlsx
    python -m uydatos hojas datos datos/planilla.xlsx Datos
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import Optional, Sequence

from uydatos import procedencia
from uydatos.errores import DatosInvalidos

# Los primeros bytes deciden el motor. El `formato` que declara el catálogo miente 23 de 24 veces y
# openpyxl se fía de la extensión: lo único que no se puede declarar mal es el contenido.
FIRMAS = {
    b"PK\x03\x04": "xlsx",  # OOXML: lo que openpyxl sabe leer
    b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1": "xls",  # OLE/BIFF: lo que sabe leer xlrd
}

# Qué lector necesita cada firma, y cómo se llama eso cuando hay que decir que falta.
MOTORES = {"xlsx": ("openpyxl", "un XLSX"), "xls": ("xlrd", "un .xls de verdad")}


class HojasInvalido(DatosInvalidos):
    """El archivo no es una planilla legible, o falta la dependencia opcional que la lee."""


def firma(ruta: Path) -> str:
    """Qué es el archivo de verdad: `xlsx`, `xls` u `otro`. Se mira la firma, no el nombre."""
    with Path(ruta).open("rb") as f:
        primeros = f.read(8)
    for marca, clase in FIRMAS.items():
        if primeros.startswith(marca):
            return clase
    return "otro"


def _abrir_xlsx(modulo: ModuleType, ruta: Path):
    """openpyxl **se fía de la extensión**: con una ruta rechaza un XLSX que se llame `.xls`. Con un
    archivo abierto no hay nombre que mirar, así que mira el contenido, que es lo que este lector
    quiere. Sin esto, el motor elegido por firma igual se caería en el nombre."""
    with Path(ruta).open("rb") as f:
        return modulo.load_workbook(f, data_only=True)


def _motor(ruta: Path) -> ModuleType:
    """El módulo que lee este archivo, importado. Si falta, lo dice con el nombre del extra."""
    clase = firma(ruta)
    if clase == "otro":
        raise HojasInvalido(
            f"{ruta}: no es un XLSX ni un XLS. La extensión no alcanza para decidirlo —el catálogo la "
            "miente 23 de cada 24 veces—, así que se mira la firma del archivo, y la firma dice otra cosa."
        )
    modulo, que_es = MOTORES[clase]
    try:
        return importlib.import_module(modulo)
    except ImportError:
        raise HojasInvalido(f"{ruta}: para leer {que_es} hace falta {modulo}: pip install uydatos[hojas]") from None


def _elegir(disponibles: list[str], hoja: Optional[str], ruta: Path) -> str:
    if hoja is None:
        return disponibles[0]
    if hoja not in disponibles:
        raise HojasInvalido(f"{ruta}: no tiene la hoja {hoja!r}. Tiene: {disponibles}")
    return hoja


def nombres(ruta: Path) -> list[str]:
    """Los nombres de las hojas, en el orden del libro."""
    modulo = _motor(ruta)
    if firma(ruta) == "xlsx":
        libro = _abrir_xlsx(modulo, ruta)
        try:
            return list(libro.sheetnames)
        finally:
            libro.close()
    return list(modulo.open_workbook(ruta).sheet_names())


def leer(ruta: Path, hoja: Optional[str] = None) -> list[list]:
    """Las filas de una hoja, con los valores ya tipados. Por defecto, la primera hoja."""
    clase = firma(ruta)
    modulo = _motor(ruta)
    if clase == "xlsx":
        libro = _abrir_xlsx(modulo, ruta)
        try:
            elegida = _elegir(list(libro.sheetnames), hoja, ruta)
            return [list(fila) for fila in libro[elegida].iter_rows(values_only=True)]
        finally:
            libro.close()
    libro = modulo.open_workbook(ruta)
    elegida = _elegir(list(libro.sheet_names()), hoja, ruta)
    planilla = libro.sheet_by_name(elegida)
    return [planilla.row_values(i) for i in range(planilla.nrows)]


def resumen(ruta: Path) -> dict:
    """El sello del archivo y la forma de cada hoja. **No sale a la red.**"""
    clase = firma(ruta)
    modulo = _motor(ruta)
    if clase == "xlsx":
        libro = _abrir_xlsx(modulo, ruta)  # sin read_only: en read_only miente con las dimensiones
        try:
            hojas = [
                {"nombre": n, "filas": libro[n].max_row, "columnas": libro[n].max_column} for n in libro.sheetnames
            ]
        finally:
            libro.close()
    else:
        libro = modulo.open_workbook(ruta)
        hojas = [
            {"nombre": n, "filas": libro.sheet_by_name(n).nrows, "columnas": libro.sheet_by_name(n).ncols}
            for n in libro.sheet_names()
        ]
    return {"sello": procedencia.sello(f"planilla {Path(ruta).name}", ruta=ruta), "firma": clase, "hojas": hojas}


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="python -m uydatos.hojas", description=__doc__.splitlines()[0])
    ordenes = p.add_subparsers(dest="orden", required=True)

    q = ordenes.add_parser("ver", help="el resumen de una planilla")
    q.add_argument("ruta", type=Path)

    q = ordenes.add_parser("datos", help="las filas de una hoja")
    q.add_argument("ruta", type=Path)
    q.add_argument("hoja", nargs="?", default=None, help="por defecto, la primera")

    args = p.parse_args(argv)
    try:
        if args.orden == "ver":
            s = resumen(args.ruta)
            print(f"firma: {s['firma']} (se miran los primeros bytes, no lo que declara el catálogo)")
            for h in s["hojas"]:
                print(f"  {h['nombre']}: {h['filas']} filas x {h['columnas']} columnas")
            print(procedencia.como_linea(s["sello"]))
        else:
            for fila in leer(args.ruta, args.hoja):
                print("\t".join("" if celda is None else str(celda) for celda in fila))
    except HojasInvalido as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
