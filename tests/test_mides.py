"""Los indicadores de MIDES: las trampas de una familia de 1.869 CSV."""

from __future__ import annotations

from pathlib import Path

import pytest

from uydatos import mides, procedencia
from uydatos.mides import MidesInvalido

CON_DIMENSIONES = "departamento,año,valor\nSalto,2000,1048612\nSalto,2001,999.5\nArtigas,2000,10\n"
SIN_DIMENSIONES = "año,valor\n2000,1048612\n2001,999\n"


def escribe(ruta: Path, texto: str, *, cp1252: bool = True) -> Path:
    """Escribe el fixture como lo publica MIDES: cp1252, salvo que el test pida UTF-8."""
    ruta.write_bytes(texto.encode("cp1252" if cp1252 else "utf-8"))
    return ruta


class TestNumeroDeIndicador:
    def test_acepta_el_numero_suelto(self):
        assert mides.numero_de_indicador("10745") == "mides-indicador-10745"

    def test_acepta_el_nombre_del_dataset(self):
        assert mides.numero_de_indicador("mides-indicador-10745") == "mides-indicador-10745"

    def test_acepta_la_url_del_dataset(self):
        url = "https://catalogodatos.gub.uy/dataset/mides-indicador-10745"
        assert mides.numero_de_indicador(url) == "mides-indicador-10745"

    def test_lo_que_no_es_un_indicador_se_rechaza(self):
        with pytest.raises(MidesInvalido, match="no parece un indicador"):
            mides.numero_de_indicador("mides-encuesta-endis")


class TestDimensiones:
    def test_un_archivo_sin_dimensiones_es_valido(self):
        assert mides.dimensiones(["año", "valor"]) == []

    def test_las_dimensiones_son_todo_menos_las_dos_ultimas(self):
        assert mides.dimensiones(["Quintiles", "Sexo", "año", "valor"]) == ["Quintiles", "Sexo"]


class TestLeerArchivo:
    def test_lee_un_archivo_con_dimensiones(self, tmp_path):
        filas = mides.leer_archivo(escribe(tmp_path / "a.csv", CON_DIMENSIONES))
        assert len(filas) == 3
        assert filas[0] == {
            "dimensiones": {"departamento": "Salto"},
            "año": 2000,
            "valor": 1048612.0,
        }

    def test_lee_un_archivo_sin_dimensiones(self, tmp_path):
        filas = mides.leer_archivo(escribe(tmp_path / "a.csv", SIN_DIMENSIONES))
        assert filas[0]["dimensiones"] == {}
        assert filas[0]["valor"] == 1048612.0

    def test_un_archivo_en_utf8_lo_detecta_el_encabezado(self, tmp_path):
        """La trampa de la codificacion: leido como cp1252, `año` se ve como `aÃ±o`."""
        ruta = escribe(tmp_path / "a.csv", CON_DIMENSIONES, cp1252=False)
        with pytest.raises(MidesInvalido, match="termina en"):
            mides.leer_archivo(ruta)

    def test_una_linea_en_blanco_se_saltea_y_se_cuenta(self, tmp_path):
        ruta = escribe(tmp_path / "a.csv", "departamento,año,valor\nSalto,2000,1\n\nSalto,2001,2\n")
        assert len(mides.leer_archivo(ruta)) == 2
        assert mides.filas_en_blanco(ruta) == 1

    def test_una_fila_con_menos_campos_se_rechaza(self, tmp_path):
        ruta = escribe(tmp_path / "a.csv", "departamento,año,valor\nSalto,2000\n")
        with pytest.raises(MidesInvalido, match="campos"):
            mides.leer_archivo(ruta)

    def test_un_valor_vacio_se_rechaza_y_no_se_rellena_con_cero(self, tmp_path):
        ruta = escribe(tmp_path / "a.csv", "departamento,año,valor\nSalto,2000,\n")
        with pytest.raises(MidesInvalido, match="no un cero"):
            mides.leer_archivo(ruta)

    def test_un_valor_que_no_es_numero_se_rechaza(self, tmp_path):
        ruta = escribe(tmp_path / "a.csv", "departamento,año,valor\nSalto,2000,sin dato\n")
        with pytest.raises(MidesInvalido, match="no es un numero"):
            mides.leer_archivo(ruta)

    def test_un_año_imposible_se_rechaza(self, tmp_path):
        ruta = escribe(tmp_path / "a.csv", "departamento,año,valor\nSalto,1200,1\n")
        with pytest.raises(MidesInvalido, match="fuera de"):
            mides.leer_archivo(ruta)

    def test_un_año_que_no_son_cuatro_digitos_se_rechaza(self, tmp_path):
        ruta = escribe(tmp_path / "a.csv", "departamento,año,valor\nSalto,siglo,1\n")
        with pytest.raises(MidesInvalido, match="cuatro digitos"):
            mides.leer_archivo(ruta)

    def test_dos_dimensiones_con_el_mismo_nombre_se_rechazan(self, tmp_path):
        """Si se repite el nombre, el diccionario se queda con una y pierde la otra en silencio."""
        ruta = escribe(tmp_path / "a.csv", "Zona,Zona,año,valor\nA,B,2000,1\n")
        with pytest.raises(MidesInvalido, match="mismo nombre"):
            mides.leer_archivo(ruta)


class TestResumen:
    def test_el_resumen_cita_el_archivo(self, tmp_path):
        ruta = escribe(tmp_path / "mides-10745.csv", CON_DIMENSIONES)
        s = mides.resumen(ruta)
        assert s["filas"] == 3
        assert s["dimensiones"] == ["departamento"]
        assert s["años"] == [2000, 2001]
        assert s["valor"] == {"min": 10.0, "max": 1048612.0}
        assert s["sello"]["sha256"] == procedencia.sha256(ruta)
        assert s["sello"]["filas"] == 3
        assert s["filas_en_blanco"] == 0
