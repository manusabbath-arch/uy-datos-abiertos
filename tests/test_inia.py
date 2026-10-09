"""Tests del lector de clima de INIA Salto Grande (segunda fuente externa).

Fijan lo que puede romperse en silencio y dar una serie creíble pero falsa:

- **`TestRechazos`**: cada defecto que el lector promete rechazar (columnas cambiadas,
  fecha duplicada, hueco, archivo vacío, valor fuera de rango físico) tiene su caso.
- **`TestNulos`**: un nulo declarado no es un cero. La lluvia de un día sin dato queda
  `None`, no `0.0`.
- **`TestNormales`**: la normal por día del año usa solo los años declarados, cierra el
  círculo del año (31/12 y 01/01 son vecinos) y cubre el 29/02.
- **`TestClimaDiario`**: la anomalía es el valor menos la normal, un nulo no produce
  anomalía inventada y el año fuera del período normal también se mide.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from uydatos.inia import (
    COLUMNAS,
    VENTANA_DIAS,
    ClimaInvalido,
    clima_diario,
    cobertura,
    dias_de_atraso,
    leer_serie,
    normales,
    tendencia_anual,
)

ENCABEZADO = ",".join(COLUMNAS)


def _escribir(dir_: Path, anio: int, filas: list[str], encabezado: str = ENCABEZADO) -> None:
    (dir_ / f"ppt_tmax_tmin_sg_{anio}.csv").write_text("\n".join([encabezado, *filas]) + "\n", encoding="utf-8")


class TestRechazos:
    def test_columnas_cambiadas(self, tmp_path):
        _escribir(tmp_path, 2020, ["2020-01-01,30.0,15.0,0.0"], "fecha,tmax,tmin,lluvia")
        with pytest.raises(ClimaInvalido, match="columnas"):
            leer_serie(tmp_path)

    def test_fecha_duplicada(self, tmp_path):
        _escribir(tmp_path, 2020, ["2020-01-01,30.0,15.0,0.0", "2020-01-01,31.0,16.0,0.0"])
        with pytest.raises(ClimaInvalido, match="duplicada"):
            leer_serie(tmp_path)

    def test_hueco_de_un_dia(self, tmp_path):
        _escribir(tmp_path, 2020, ["2020-01-01,30.0,15.0,0.0", "2020-01-03,30.0,15.0,0.0"])
        with pytest.raises(ClimaInvalido, match="hueco"):
            leer_serie(tmp_path)

    def test_hueco_entre_anios(self, tmp_path):
        _escribir(tmp_path, 2020, ["2020-12-30,30.0,15.0,0.0"])
        _escribir(tmp_path, 2021, ["2021-01-02,30.0,15.0,0.0"])
        with pytest.raises(ClimaInvalido, match="hueco"):
            leer_serie(tmp_path)

    def test_archivo_sin_filas_de_datos(self, tmp_path):
        _escribir(tmp_path, 2020, [])
        with pytest.raises(ClimaInvalido, match="sin filas"):
            leer_serie(tmp_path)

    def test_directorio_sin_archivos(self, tmp_path):
        with pytest.raises(ClimaInvalido, match="ningún archivo"):
            leer_serie(tmp_path)

    def test_fecha_fuera_del_anio_del_archivo(self, tmp_path):
        _escribir(tmp_path, 2020, ["2019-12-31,30.0,15.0,0.0"])
        with pytest.raises(ClimaInvalido, match="año"):
            leer_serie(tmp_path)

    def test_fecha_ilegible(self, tmp_path):
        _escribir(tmp_path, 2020, ["01/01/2020,30.0,15.0,0.0"])
        with pytest.raises(ClimaInvalido, match="fecha"):
            leer_serie(tmp_path)

    def test_tmax_menor_que_tmin(self, tmp_path):
        _escribir(tmp_path, 2020, ["2020-01-01,10.0,15.0,0.0"])
        with pytest.raises(ClimaInvalido, match="tmax"):
            leer_serie(tmp_path)

    def test_lluvia_negativa(self, tmp_path):
        _escribir(tmp_path, 2020, ["2020-01-01,30.0,15.0,-1.0"])
        with pytest.raises(ClimaInvalido, match="lluvia"):
            leer_serie(tmp_path)

    def test_temperatura_imposible(self, tmp_path):
        _escribir(tmp_path, 2020, ["2020-01-01,90.0,15.0,0.0"])
        with pytest.raises(ClimaInvalido, match="rango"):
            leer_serie(tmp_path)

    def test_numero_ilegible(self, tmp_path):
        _escribir(tmp_path, 2020, ["2020-01-01,abc,15.0,0.0"])
        with pytest.raises(ClimaInvalido, match="número"):
            leer_serie(tmp_path)


class TestNulos:
    def test_lluvia_vacia_queda_none_y_no_cero(self, tmp_path):
        _escribir(tmp_path, 2020, ["2020-01-01,30.0,15.0,", "2020-01-02,30.0,15.0,0.0"])
        serie = leer_serie(tmp_path)
        assert serie[0]["pluviometro"] is None
        assert serie[1]["pluviometro"] == 0.0

    def test_cobertura_cuenta_el_nulo(self, tmp_path):
        _escribir(tmp_path, 2020, ["2020-01-01,30.0,15.0,", "2020-01-02,30.0,15.0,0.0"])
        c = cobertura(leer_serie(tmp_path))
        assert c["nulos"] == {"temperaturaMaxima": 0, "temperaturaMinima": 0, "pluviometro": 1}


class TestCobertura:
    def test_denominador_y_extremos(self, tmp_path):
        _escribir(tmp_path, 2020, [f"2020-01-{d:02d},30.0,15.0,0.0" for d in range(1, 11)])
        c = cobertura(leer_serie(tmp_path))
        assert c["filas"] == 10
        assert c["esperado"] == 10
        assert str(c["primera"]) == "2020-01-01"
        assert str(c["ultima"]) == "2020-01-10"

    def test_serie_vacia_no_se_mide(self):
        with pytest.raises(ClimaInvalido, match="vacía"):
            cobertura([])


def _serie_sintetica(anios, valor):
    """Serie diaria completa; `valor(fecha)` da la tmax, la tmin es tmax - 5, lluvia 0."""
    serie = []
    for anio in anios:
        d = date(anio, 1, 1)
        while d.year == anio:
            t = valor(d)
            serie.append({"fecha": d, "temperaturaMaxima": t, "temperaturaMinima": t - 5.0, "pluviometro": 0.0})
            d += timedelta(days=1)
    return serie


class TestNormales:
    def test_serie_constante_da_normal_constante(self):
        serie = _serie_sintetica(range(2000, 2005), lambda d: 25.0)
        n = normales(serie, 2000, 2004)
        assert len(n) == 366
        assert all(v["tmax"] == pytest.approx(25.0) for v in n.values())

    def test_solo_usa_los_anios_declarados(self):
        serie = _serie_sintetica(range(2000, 2005), lambda d: 10.0 if d.year < 2004 else 99.0)
        n = normales(serie, 2000, 2003)
        assert n[(6, 15)]["tmax"] == pytest.approx(10.0)

    def test_el_anio_cierra_el_circulo(self):
        # Con ventana, el 01/01 debe ver al 31/12 como vecino.
        def valor(d):
            return 40.0 if (d.month, d.day) == (12, 31) else 20.0

        serie = _serie_sintetica(range(2000, 2004), valor)
        n = normales(serie, 2000, 2003)
        assert n[(1, 1)]["tmax"] > 20.0

    def test_29_de_febrero_tiene_normal(self):
        serie = _serie_sintetica(range(2000, 2005), lambda d: 25.0)
        assert (2, 29) in normales(serie, 2000, 2004)

    def test_informa_cuantas_muestras_uso(self):
        serie = _serie_sintetica(range(2000, 2005), lambda d: 25.0)
        n = normales(serie, 2000, 2004)
        assert n[(6, 15)]["n"] >= 5 * (2 * VENTANA_DIAS)

    def test_periodo_sin_datos_no_se_calcula(self):
        serie = _serie_sintetica(range(2000, 2003), lambda d: 25.0)
        with pytest.raises(ClimaInvalido, match="período"):
            normales(serie, 1990, 1995)


class TestClimaDiario:
    def test_anomalia_es_valor_menos_normal(self):
        serie = _serie_sintetica(range(2000, 2005), lambda d: 30.0 if d.year == 2004 else 20.0)
        filas = clima_diario(serie, 2000, 2003)
        f = next(x for x in filas if str(x["fecha"]) == "2004-06-15")
        assert f["anom_tmax"] == pytest.approx(10.0)
        assert f["anom_tmin"] == pytest.approx(10.0)

    def test_nulo_no_inventa_anomalia(self):
        serie = _serie_sintetica(range(2000, 2003), lambda d: 20.0)
        serie[10]["temperaturaMaxima"] = None
        filas = clima_diario(serie, 2000, 2002)
        assert filas[10]["anom_tmax"] is None
        assert filas[10]["anom_tmin"] is not None

    def test_una_fila_por_dia_de_la_serie(self):
        serie = _serie_sintetica(range(2000, 2003), lambda d: 20.0)
        assert len(clima_diario(serie, 2000, 2002)) == len(serie)


class TestAtraso:
    def test_dias_de_atraso(self):
        serie = _serie_sintetica(range(2020, 2021), lambda d: 20.0)
        assert dias_de_atraso(serie, date(2021, 1, 10)) == 10

    def test_serie_vacia_no_se_mide(self):
        with pytest.raises(ClimaInvalido, match="vacía"):
            dias_de_atraso([], date(2021, 1, 10))


class TestTendencia:
    def test_recta_perfecta(self):
        # tmax sube 0,03 C por anio = 0,3 C por decada, sin ruido
        serie = _serie_sintetica(range(2000, 2010), lambda d: 20.0 + 0.03 * (d.year - 2000))
        t = tendencia_anual(serie, 2000, 2009)["tmax"]
        assert t["por_decada"] == pytest.approx(0.3)
        assert t["error_estandar"] == pytest.approx(0.0, abs=1e-9)

    def test_serie_plana(self):
        serie = _serie_sintetica(range(2000, 2010), lambda d: 20.0)
        assert tendencia_anual(serie, 2000, 2009)["tmax"]["por_decada"] == pytest.approx(0.0)

    def test_pocos_anios_no_se_mide(self):
        serie = _serie_sintetica(range(2000, 2002), lambda d: 20.0)
        with pytest.raises(ClimaInvalido, match="años"):
            tendencia_anual(serie, 2000, 2001)

    def test_solo_cuenta_anios_completos(self):
        serie = _serie_sintetica(range(2000, 2005), lambda d: 20.0)
        serie = [f for f in serie if not (f["fecha"].year == 2004 and f["fecha"].month > 6)]
        with pytest.raises(ClimaInvalido, match="años"):
            tendencia_anual(serie, 2003, 2004)
