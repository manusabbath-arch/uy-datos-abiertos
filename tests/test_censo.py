"""Tests de `uydatos.censo`: los tabulados de población del Censo 2023 (INE), sin red.

Los libros se arman acá con la misma forma que los cuadros reales (título, encabezado en la fila 4,
fila de total, notas al pie): lo que se fija es lo que puede romperse en silencio.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from uydatos import censo
from uydatos.censo import CensoInvalido

openpyxl = pytest.importorskip("openpyxl")


def _libro(ruta: Path, filas: list[tuple]) -> Path:
    libro = openpyxl.Workbook()
    hoja = libro.active
    for fila in filas:
        hoja.append(list(fila))
    libro.save(ruta)
    return ruta


ENCABEZADO_13 = ("Código localidad INE", "Nombre departamento", "Nombre localidad", "Población Total")
PIE = [
    (None, None, None, None),
    ("Fuente: Instituto Nacional de Estadística (INE) - Censos 2023.", None, None, None),
    ("Notas: ", None, None, None),
    ("     Datos ponderados.", None, None, None),
]


def cuadro_13(ruta: Path, total: int = 112527 + 7543 + 79457, filas=None) -> Path:
    datos = filas or [
        ("15120", "SALTO", "SALTO", 112527),
        ("15900", "SALTO", "RURAL/PARAJE RURAL", 7543),
        ("11120", "PAYSANDÚ", "PAYSANDU", 79457),
    ]
    return _libro(
        ruta,
        [
            ("CUADRO 13", None, None, None),
            ("Población por departamento y localidad. Total País.", None, None, None),
            (None, None, None, None),
            ENCABEZADO_13,
            (None, None, None, None),
            ("Total", None, None, total),
            (None, None, None, None),
            *datos,
            *PIE,
        ],
    )


def cuadro_12(ruta: Path, filas=None) -> Path:
    datos = filas or [("11", "PAYSANDU", 121838, 13922, 8.75), ("15", "SALTO", 136195, 14163, 9.61)]
    return _libro(
        ruta,
        [
            ("CUADRO 12", None, None, None, None),
            ("Población, área (km2) y densidad por departamento. Total País.", None, None, None, None),
            (None, None, None, None, None),
            ("Código Localidad INE 2023", "Departamento", "Población Total", "Área (Km2)", "Densidad (Hb/km2)"),
            *datos,
            (None, None, None, None, None),
            ("Fuente: Instituto Nacional de Estadística (INE) - Censos 2023.", None, None, None, None),
        ],
    )


class TestLocalidades:
    def test_lee_las_filas_de_dato_y_saltea_titulo_total_y_notas(self, tmp_path):
        filas = censo.leer_localidades(cuadro_13(tmp_path / "c13.xlsx"))
        assert filas[0] == {"codigo": "15120", "departamento": "SALTO", "localidad": "SALTO", "poblacion": 112527}
        assert [f["codigo"] for f in filas] == ["15120", "15900", "11120"]

    def test_las_filas_sin_dato_de_localidad_no_salen_pero_cierran_el_total(self, tmp_path):
        filas = [("15120", "SALTO", "SALTO", 10), ("-", "CANELONES", "CANELONES - Sin dato localidad", 234)]
        salida = censo.leer_localidades(cuadro_13(tmp_path / "c13.xlsx", total=244, filas=filas))
        assert [f["codigo"] for f in salida] == ["15120"]
        with pytest.raises(CensoInvalido, match="234 sin dato"):
            censo.leer_localidades(cuadro_13(tmp_path / "c13b.xlsx", total=10, filas=filas))

    def test_un_total_que_no_cierra_rechaza_el_archivo(self, tmp_path):
        with pytest.raises(CensoInvalido, match="total"):
            censo.leer_localidades(cuadro_13(tmp_path / "c13.xlsx", total=1))

    def test_un_codigo_repetido_rechaza(self, tmp_path):
        filas = [("15120", "SALTO", "SALTO", 10), ("15120", "SALTO", "OTRA", 5)]
        with pytest.raises(CensoInvalido, match="repetido"):
            censo.leer_localidades(cuadro_13(tmp_path / "c13.xlsx", total=15, filas=filas))

    def test_una_poblacion_que_no_es_entera_rechaza(self, tmp_path):
        filas = [("15120", "SALTO", "SALTO", "s/d")]
        with pytest.raises(CensoInvalido, match="15120"):
            censo.leer_localidades(cuadro_13(tmp_path / "c13.xlsx", total=0, filas=filas))

    def test_otro_encabezado_es_otro_cuadro(self, tmp_path):
        ruta = _libro(tmp_path / "x.xlsx", [("CUADRO 1", None), ("Departamento", "Población")])
        with pytest.raises(CensoInvalido, match="encabezado"):
            censo.leer_localidades(ruta)


class TestDepartamentos:
    def test_lee_poblacion_y_area(self, tmp_path):
        filas = censo.leer_departamentos(cuadro_12(tmp_path / "c12.xlsx"))
        assert filas[0] == {"codigo": "11", "departamento": "PAYSANDU", "poblacion": 121838, "area_km2": 13922}

    def test_un_codigo_que_no_es_de_departamento_rechaza(self, tmp_path):
        with pytest.raises(CensoInvalido, match="código"):
            censo.leer_departamentos(cuadro_12(tmp_path / "c12.xlsx", filas=[("115", "SALTO", 1, 1, 1.0)]))

    def test_un_cuadro_sin_filas_rechaza(self, tmp_path):
        with pytest.raises(CensoInvalido, match="ninguna fila"):
            censo.leer_departamentos(cuadro_12(tmp_path / "c12.xlsx", filas=[(None, None, None, None, None)]))


def test_las_urls_son_las_de_los_tabulados_del_ine():
    assert censo.URLS["localidades"].endswith("Cuadro_13_CAR_2023.xlsx")
    assert censo.URLS["departamentos"].endswith("Cuadro_12_CAR_2023.xlsx")
