"""Las hojas de cálculo: manda la firma del archivo, no lo que dice el catálogo.

Medido el 10/10/26 sobre 24 recursos que el catálogo declara `XLS`: **23 son en realidad XLSX** —el
recurso se llama `.xlsx` y su contenido es el ZIP de OOXML— y el único `.xls` OLE de verdad de la
muestra es el de AGESIC. El metadato `formato` no alcanza para elegir el motor, así que se elige por
los primeros bytes del archivo.

Las dependencias son opcionales a propósito (el paquete base no engorda): estos tests se saltean si
falta `openpyxl`, y para correrlos de verdad hay que dárselo.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from uydatos import hojas
from uydatos.hojas import HojasInvalido

openpyxl = pytest.importorskip("openpyxl")

FIRMA_OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def libro_de_prueba(ruta: Path) -> Path:
    """Un XLSX mínimo, con la forma que usa MIDES: hoja `Datos` y hoja `Metadatos`."""
    libro = openpyxl.Workbook()
    datos = libro.active
    datos.title = "Datos"
    for fila in (("año", "valor"), (2010, 10880), (2011, 11996)):
        datos.append(fila)
    metadatos = libro.create_sheet("Metadatos")
    metadatos.append(("nombreDeAtributo", "descripcion", "tipoDeDato"))
    metadatos.append(("año", "año", "Number"))
    libro.save(ruta)
    libro.close()
    return ruta


class TestFirma:
    def test_un_xlsx_de_verdad(self, tmp_path: Path) -> None:
        assert hojas.firma(libro_de_prueba(tmp_path / "a.xlsx")) == "xlsx"

    def test_un_xlsx_renombrado_a_xls_sigue_siendo_xlsx(self, tmp_path: Path) -> None:
        """El motor sale de la firma, así que el nombre no lo confunde."""
        ruta = libro_de_prueba(tmp_path / "a.xls")
        assert hojas.firma(ruta) == "xlsx"

    def test_la_firma_de_un_xls_de_verdad(self, tmp_path: Path) -> None:
        ruta = tmp_path / "a.xls"
        ruta.write_bytes(FIRMA_OLE + b"\x00" * 64)
        assert hojas.firma(ruta) == "xls"

    def test_cualquier_otra_cosa_es_otro(self, tmp_path: Path) -> None:
        ruta = tmp_path / "a.xls"
        ruta.write_bytes(b"esto no es una planilla")
        assert hojas.firma(ruta) == "otro"


class TestNombresYFilas:
    def test_las_hojas_del_libro(self, tmp_path: Path) -> None:
        assert hojas.nombres(libro_de_prueba(tmp_path / "a.xlsx")) == ["Datos", "Metadatos"]

    def test_lee_la_primera_hoja_por_defecto(self, tmp_path: Path) -> None:
        filas = hojas.leer(libro_de_prueba(tmp_path / "a.xlsx"))
        assert filas[0] == ["año", "valor"]
        assert filas[1] == [2010, 10880]  # los números vienen tipados, no como texto

    def test_lee_una_hoja_por_nombre(self, tmp_path: Path) -> None:
        filas = hojas.leer(libro_de_prueba(tmp_path / "a.xlsx"), "Metadatos")
        assert filas[0] == ["nombreDeAtributo", "descripcion", "tipoDeDato"]

    def test_lee_un_xlsx_que_se_llama_xls(self, tmp_path: Path) -> None:
        """Defensivo: si un recurso viniera con el nombre mentido, openpyxl lo rechazaría por mirar
        la extensión. Se le pasa el archivo abierto, así que lee el contenido igual."""
        filas = hojas.leer(libro_de_prueba(tmp_path / "a.xls"))
        assert filas[1] == [2010, 10880]

    def test_una_hoja_que_no_existe_lo_dice(self, tmp_path: Path) -> None:
        with pytest.raises(HojasInvalido, match="no tiene la hoja"):
            hojas.leer(libro_de_prueba(tmp_path / "a.xlsx"), "NoExiste")

    def test_un_archivo_que_no_es_planilla_se_rechaza(self, tmp_path: Path) -> None:
        ruta = tmp_path / "a.xlsx"
        ruta.write_bytes(b"no soy una planilla")
        with pytest.raises(HojasInvalido, match="no es un XLSX ni un XLS"):
            hojas.leer(ruta)


class TestResumen:
    def test_el_resumen_dice_la_firma_real_y_la_forma_de_cada_hoja(self, tmp_path: Path) -> None:
        ruta = libro_de_prueba(tmp_path / "a.xls")  # mentida a propósito
        s = hojas.resumen(ruta)
        assert s["firma"] == "xlsx"
        assert [h["nombre"] for h in s["hojas"]] == ["Datos", "Metadatos"]
        assert s["hojas"][0]["filas"] == 3
        assert s["hojas"][0]["columnas"] == 2
        assert s["sello"]["sha256"], "el resumen cita el archivo, así que tiene que sellarlo"


class TestLaDependenciaOpcional:
    def test_si_falta_openpyxl_lo_dice_con_el_nombre_del_extra(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ruta = libro_de_prueba(tmp_path / "a.xlsx")
        monkeypatch.setitem(sys.modules, "openpyxl", None)
        with pytest.raises(HojasInvalido, match=r"pip install uydatos\[hojas\]"):
            hojas.leer(ruta)

    def test_si_falta_xlrd_lo_dice_con_el_nombre_del_extra(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ruta = tmp_path / "a.xls"
        ruta.write_bytes(FIRMA_OLE + b"\x00" * 64)
        monkeypatch.setitem(sys.modules, "xlrd", None)
        with pytest.raises(HojasInvalido, match=r"pip install uydatos\[hojas\]"):
            hojas.leer(ruta)
