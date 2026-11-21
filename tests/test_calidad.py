"""Las marcas de calidad de una serie: rango, plano, salto y sin dato, sin corregir nada."""

from __future__ import annotations

import math

import pytest

from uydatos import calidad


class TestMarcar:
    def test_una_serie_limpia_sale_toda_ok(self):
        valores = [1.0, 1.1, 1.2, 1.25, 1.3]
        assert calidad.marcar(valores, minimo=0, maximo=5, max_salto=0.5) == [calidad.OK] * 5

    def test_fuera_de_rango(self):
        """Una altura de 90 m en el rio Uruguay no es un evento: es una lectura rota."""
        marcas = calidad.marcar([1.0, 90.0, 1.1], minimo=0, maximo=10, max_salto=None)
        assert marcas == [calidad.OK, calidad.RANGO, calidad.OK]

    def test_plano_marca_desde_la_repeticion_pedida(self):
        """Un sensor congelado repite el mismo valor: las primeras lecturas no lo delatan."""
        marcas = calidad.marcar([2.0] * 8, minimo=0, maximo=10, repeticiones=6)
        assert marcas == [calidad.OK] * 5 + [calidad.PLANO] * 3

    def test_un_hueco_corta_la_racha(self):
        marcas = calidad.marcar([2.0, 2.0, None, 2.0, 2.0], minimo=0, maximo=10, repeticiones=3)
        assert marcas == [calidad.OK, calidad.OK, calidad.SIN_DATO, calidad.OK, calidad.OK]

    def test_salto_contra_la_lectura_anterior(self):
        marcas = calidad.marcar([1.0, 1.05, 3.0, 3.05], minimo=0, maximo=10, max_salto=0.5)
        assert marcas == [calidad.OK, calidad.OK, calidad.SALTO, calidad.OK]

    def test_el_salto_se_mide_contra_la_ultima_lectura_valida(self):
        """Con un hueco en el medio, la vuelta no es un salto si el valor no se movio."""
        marcas = calidad.marcar([1.0, None, 1.05], minimo=0, maximo=10, max_salto=0.5)
        assert marcas == [calidad.OK, calidad.SIN_DATO, calidad.OK]

    def test_sin_max_salto_no_se_prueba_el_salto(self):
        assert calidad.marcar([1.0, 90.0], minimo=0, maximo=10, max_salto=None)[1] == calidad.RANGO
        assert calidad.marcar([1.0, 9.0], minimo=0, maximo=10, max_salto=None) == [calidad.OK, calidad.OK]

    def test_nan_es_sin_dato(self):
        marcas = calidad.marcar([1.0, float("nan"), 1.2], minimo=0, maximo=10)
        assert marcas == [calidad.OK, calidad.SIN_DATO, calidad.OK]

    def test_el_rango_gana_sobre_el_plano(self):
        """Un valor fuera de rango repetido sigue siendo rango, no un sensor trabado."""
        marcas = calidad.marcar([90.0] * 4, minimo=0, maximo=10, repeticiones=2)
        assert marcas == [calidad.RANGO] * 4

    def test_los_limites_tienen_que_encerrar_un_rango(self):
        with pytest.raises(ValueError, match="no encierran un rango"):
            calidad.marcar([1.0], minimo=10, maximo=10)

    def test_repeticiones_menores_a_dos_se_rechazan(self):
        with pytest.raises(ValueError, match="repeticiones"):
            calidad.marcar([1.0], minimo=0, maximo=10, repeticiones=1)

    def test_un_max_salto_no_positivo_se_rechaza(self):
        with pytest.raises(ValueError, match="max_salto"):
            calidad.marcar([1.0], minimo=0, maximo=10, max_salto=0)

    def test_una_marca_por_valor_y_en_orden(self):
        valores = [1.0, None, 90.0, 1.0]
        marcas = calidad.marcar(valores, minimo=0, maximo=10)
        assert len(marcas) == len(valores)


class TestResumen:
    def test_cuenta_cada_marca_con_las_cinco_claves(self):
        marcas = [calidad.OK, calidad.OK, calidad.PLANO, calidad.SIN_DATO]
        assert calidad.resumen(marcas) == {"ok": 2, "rango": 0, "plano": 1, "salto": 0, "sin_dato": 1}

    def test_una_marca_inventada_se_rechaza(self):
        with pytest.raises(ValueError, match="marca desconocida"):
            calidad.resumen(["ok", "rara"])


class TestSugerirLimites:
    def test_estirado_sobre_la_serie(self):
        r = calidad.sugerir_limites([1.0, 2.0, 3.0, 4.0])
        assert (r["minimo"], r["maximo"]) == (-0.5, 5.5)  # 3 de amplitud, 50% para cada lado
        assert r["lecturas"] == 4 and r["max_salto"] == 6.0  # el tipico es 1.0
        assert "revisar" in r["nota"]

    def test_el_salto_tipico_no_se_deja_arrastrar_por_un_pico(self):
        r = calidad.sugerir_limites([1.0, 1.1, 1.2, 1.3, 60.0])
        assert r["max_salto"] is not None and r["max_salto"] < 60.0

    def test_sin_variacion_no_hay_salto_que_sugerir(self):
        assert calidad.sugerir_limites([2.0, 2.0, 2.0])["max_salto"] is None

    def test_menos_de_tres_lecturas_se_rechaza(self):
        with pytest.raises(ValueError, match="3 lecturas"):
            calidad.sugerir_limites([1.0, None])

    def test_un_nan_no_entra_a_los_limites(self):
        r = calidad.sugerir_limites([1.0, math.nan, 3.0, 5.0])
        assert r["lecturas"] == 3 and r["maximo"] > 5.0
