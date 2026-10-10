"""Tests del lector de observaciones meteorológicas de INUMET.

Fijan lo que puede romperse en silencio y dar una serie creíble pero falsa:

- **`TestRechazos`**: cada defecto que el lector promete rechazar tiene su caso. El que importa
  es el de la estación: los dos archivos reales traen una fila con el texto de un error del
  servidor en la columna de la estación.
- **`TestNulos`**: un valor vacío es un nulo, no un cero, y una fila `;;` es un separador.
- **`TestDiaria`**: el día es **local** (UTC−3), no UTC; un día incompleto queda en `None` con
  sus horas declaradas; la agregación la elige quien llama, no el paquete.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from uydatos.inumet import (
    DATASETS,
    DESFASE_LOCAL,
    ESTACIONES,
    InumetInvalido,
    filas_sin_dato,
    leer_archivo,
    resumen,
    serie_diaria,
    valor_por_estacion,
)

ENCABEZADO = "fecha;estacion_id;temp_aire"


def _escribir(ruta: Path, filas: list[str], encabezado: str = ENCABEZADO) -> None:
    ruta.write_text("\n".join([encabezado, *filas]) + "\n", encoding="utf-8")


def _bloque(inicio: datetime, n: int = 24, estacion: str = "Salto G3", valor: str = "20.0") -> list[str]:
    return [f"{(inicio + timedelta(hours=i)).strftime('%Y-%m-%d %H:%M')};{estacion};{valor}" for i in range(n)]


class TestRechazos:
    def test_columnas_cambiadas(self, tmp_path):
        ruta = tmp_path / "t.csv"
        _escribir(ruta, _bloque(datetime(2020, 1, 1)), "fecha;estacion;temp")
        with pytest.raises(InumetInvalido, match="columnas"):
            leer_archivo(ruta, ("temp_aire",))

    def test_archivo_sin_filas_de_datos(self, tmp_path):
        ruta = tmp_path / "t.csv"
        _escribir(ruta, [])
        with pytest.raises(InumetInvalido, match="sin filas"):
            leer_archivo(ruta, ("temp_aire",))

    def test_la_fila_con_el_error_del_servidor_no_es_fila_de_dato(self, tmp_path):
        """Medido el 09/10/26: los dos archivos reales traen `' please try again later.'` sin fecha.

        Se saltea y se cuenta; no se descarta en silencio ni crea una octava estación.
        """
        ruta = tmp_path / "t.csv"
        _escribir(ruta, ["; please try again later.;", *_bloque(datetime(2020, 1, 1))])
        assert len(leer_archivo(ruta, ("temp_aire",))) == 24
        assert filas_sin_dato(ruta) == 1

    def test_una_estacion_desconocida_con_fecha_se_rechaza(self, tmp_path):
        ruta = tmp_path / "t.csv"
        _escribir(ruta, ["2020-01-01 00:00;Estación Fantasma;20.0"])
        with pytest.raises(InumetInvalido, match="desconocida"):
            leer_archivo(ruta, ("temp_aire",))

    def test_fecha_ilegible(self, tmp_path):
        ruta = tmp_path / "t.csv"
        _escribir(ruta, ["2020-01-01;Salto G3;20.0"])
        with pytest.raises(InumetInvalido, match="fecha ilegible"):
            leer_archivo(ruta, ("temp_aire",))

    def test_numero_ilegible(self, tmp_path):
        ruta = tmp_path / "t.csv"
        _escribir(ruta, ["2020-01-01 00:00;Salto G3;S/D"])
        with pytest.raises(InumetInvalido, match="ilegible"):
            leer_archivo(ruta, ("temp_aire",))

    def test_temperatura_imposible(self, tmp_path):
        ruta = tmp_path / "t.csv"
        _escribir(ruta, ["2020-01-01 00:00;Salto G3;999.0"])
        with pytest.raises(InumetInvalido, match="rango"):
            leer_archivo(ruta, ("temp_aire",))

    def test_hora_repetida_en_la_misma_estacion(self, tmp_path):
        ruta = tmp_path / "t.csv"
        _escribir(ruta, ["2020-01-01 00:00;Salto G3;20.0", "2020-01-01 00:00;Salto G3;21.0"])
        with pytest.raises(InumetInvalido, match="repetida"):
            leer_archivo(ruta, ("temp_aire",))

    def test_la_variable_diaria_no_se_agrega_por_hora(self, tmp_path):
        ruta = tmp_path / "h.csv"
        _escribir(
            ruta, ["2023-10-02 00:00;Rocha G3;7.6", "2023-10-03 00:00;Rocha G3;9.6"], "fecha;estacion_id;heliofania"
        )
        with pytest.raises(InumetInvalido, match="horaria"):
            valor_por_estacion(ruta, "insolacion")


class TestNulos:
    def test_valor_vacio_es_none_y_no_cero(self, tmp_path):
        ruta = tmp_path / "t.csv"
        _escribir(ruta, ["2020-01-01 00:00;Salto G3;"])
        assert leer_archivo(ruta, ("temp_aire",))[0]["temp_aire"] is None

    def test_las_filas_en_blanco_son_separadores(self, tmp_path):
        """Medido el 09/10/26: siete filas `;;` en cada archivo, la última incluida."""
        ruta = tmp_path / "t.csv"
        _escribir(ruta, [";;", *_bloque(datetime(2020, 1, 1), n=2), ";;"])
        assert len(leer_archivo(ruta, ("temp_aire",))) == 2
        assert filas_sin_dato(ruta) == 2


class TestVariasColumnas:
    def test_el_viento_trae_dos_columnas_de_valor(self, tmp_path):
        ruta = tmp_path / "v.csv"
        _escribir(ruta, ["2020-01-01 01:00;Aeropuerto Melilla G3;147;12"], "fecha;estacion_id;dir_viento;int_viento")
        fila = leer_archivo(ruta, DATASETS["viento"][1])[0]
        assert (fila["dir_viento"], fila["int_viento"]) == (147.0, 12.0)


class TestDiaria:
    def test_el_dia_es_local_y_arranca_a_las_03_utc(self, tmp_path):
        """Uruguay es UTC−3: el día local 01/01 va de las 03:00 UTC a las 02:00 UTC del 02/01."""
        ruta = tmp_path / "t.csv"
        _escribir(ruta, _bloque(datetime(2020, 1, 1, 3, 0)))
        serie = leer_archivo(ruta, ("temp_aire",))
        (dia,) = serie_diaria(serie, "Salto G3", "temp_aire", "max")
        assert dia["fecha"].isoformat() == "2020-01-01" and dia["horas"] == 24 and dia["valor"] == 20.0

    def test_con_desfase_cero_el_mismo_bloque_son_dos_dias_incompletos(self, tmp_path):
        ruta = tmp_path / "t.csv"
        _escribir(ruta, _bloque(datetime(2020, 1, 1, 3, 0)))
        serie = leer_archivo(ruta, ("temp_aire",))
        dias = serie_diaria(serie, "Salto G3", "temp_aire", "max", desfase_horas=0)
        assert [d["horas"] for d in dias] == [21, 3]
        assert all(d["valor"] is None for d in dias)

    def test_un_dia_al_que_le_falta_una_hora_no_es_un_dia(self, tmp_path):
        ruta = tmp_path / "t.csv"
        _escribir(ruta, _bloque(datetime(2020, 1, 1, 3, 0), n=23))
        (dia,) = serie_diaria(leer_archivo(ruta, ("temp_aire",)), "Salto G3", "temp_aire", "max")
        assert dia["valor"] is None and dia["horas"] == 23

    def test_una_hora_nula_tambien_deja_el_dia_en_none(self, tmp_path):
        ruta = tmp_path / "t.csv"
        filas = _bloque(datetime(2020, 1, 1, 3, 0))
        filas[0] = ";".join(filas[0].split(";")[:2] + [""])
        _escribir(ruta, filas)
        (dia,) = serie_diaria(leer_archivo(ruta, ("temp_aire",)), "Salto G3", "temp_aire", "max")
        assert dia["valor"] is None and (dia["horas"], dia["nulos"]) == (24, 1)

    def test_las_agregaciones(self, tmp_path):
        ruta = tmp_path / "p.csv"
        filas = [
            f"{(datetime(2020, 1, 1, 3, 0) + timedelta(hours=i)).strftime('%Y-%m-%d %H:%M')};Salto G3;{i}"
            for i in range(24)
        ]
        _escribir(ruta, filas, "fecha;estacion_id;precip_horario")
        serie = leer_archivo(ruta, ("precip_horario",))
        assert serie_diaria(serie, "Salto G3", "precip_horario", "suma")[0]["valor"] == 276.0
        assert serie_diaria(serie, "Salto G3", "precip_horario", "max")[0]["valor"] == 23.0
        assert serie_diaria(serie, "Salto G3", "precip_horario", "min")[0]["valor"] == 0.0
        assert serie_diaria(serie, "Salto G3", "precip_horario", "promedio")[0]["valor"] == 11.5

    def test_la_agregacion_no_tiene_default(self, tmp_path):
        ruta = tmp_path / "t.csv"
        _escribir(ruta, _bloque(datetime(2020, 1, 1)))
        serie = leer_archivo(ruta, ("temp_aire",))
        with pytest.raises(TypeError):
            serie_diaria(serie, "Salto G3", "temp_aire")  # type: ignore[call-arg]

    def test_agregacion_desconocida(self, tmp_path):
        ruta = tmp_path / "t.csv"
        _escribir(ruta, _bloque(datetime(2020, 1, 1)))
        serie = leer_archivo(ruta, ("temp_aire",))
        with pytest.raises(InumetInvalido, match="agregación"):
            serie_diaria(serie, "Salto G3", "temp_aire", "mediana")

    def test_estacion_sin_filas_no_se_mide(self, tmp_path):
        ruta = tmp_path / "t.csv"
        _escribir(ruta, _bloque(datetime(2020, 1, 1), estacion="Rocha G3"))
        serie = leer_archivo(ruta, ("temp_aire",))
        with pytest.raises(InumetInvalido, match="no tiene filas"):
            serie_diaria(serie, "Salto G3", "temp_aire", "max")


class TestResumen:
    def test_cuenta_por_estacion_nulos_y_dias_completos(self, tmp_path):
        ruta = tmp_path / "t.csv"
        filas = [
            *_bloque(datetime(2020, 1, 1, 3, 0), n=24, estacion="Salto G3"),
            *_bloque(datetime(2020, 1, 2, 3, 0), n=23, estacion="Salto G3"),
            *_bloque(datetime(2020, 1, 1, 3, 0), n=1, estacion="Rocha G3"),
        ]
        _escribir(ruta, filas)
        r = resumen(leer_archivo(ruta, ("temp_aire",)))
        assert r["filas"] == 48
        assert r["estaciones"]["Salto G3"]["dias"] == 2
        assert r["estaciones"]["Salto G3"]["dias_completos"] == 1
        assert r["estaciones"]["Rocha G3"]["dias_completos"] == 0

    def test_serie_vacia_no_se_mide(self):
        with pytest.raises(InumetInvalido, match="vacía"):
            resumen([])

    def test_desfase_local_es_utc_menos_tres(self):
        assert DESFASE_LOCAL == -3

    def test_las_siete_estaciones_del_metadato(self):
        assert len(ESTACIONES) == 7 and "Salto G3" in ESTACIONES
