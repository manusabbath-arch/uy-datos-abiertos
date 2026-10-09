"""Tests de `uydatos.semanas` — semanas ISO con etiqueta W1, W2...

Semana ISO 8601: de lunes a domingo, y la W1 de un año es la que tiene su primer jueves. Es la que usan
MercadoLibre y PedidosYa para comunicar semanas, y la que trae `date.isocalendar()`.

- **`TestEtiqueta`**: W41 para el 09/10/2026 (viernes).
- **`TestBordeDeAnio`**: el año de la semana no siempre es el del calendario: el 01/01/2027 (viernes)
  pertenece a la **2026-W53**, y el 29/12/2025 (lunes) a la **2026-W01**. Por eso la etiqueta larga lleva
  el año ISO, no el del día.
- **`TestRango`**: de una etiqueta se vuelve a sus siete días, y al revés.
"""

from __future__ import annotations

from datetime import date

import pytest

from uydatos.semanas import (
    Semana,
    etiqueta,
    etiqueta_con_dias,
    semana_de,
    semanas_del_anio,
    semanas_entre,
)


class TestEtiqueta:
    def test_w41(self):
        assert etiqueta(date(2026, 10, 9)) == "W41"
        assert etiqueta(date(2026, 10, 9), con_anio=True) == "2026-W41"

    def test_lunes_y_domingo_son_la_misma_semana(self):
        assert etiqueta(date(2026, 10, 5)) == etiqueta(date(2026, 10, 11)) == "W41"

    def test_sin_cero_adelante(self):
        assert etiqueta(date(2026, 1, 7)) == "W2"
        assert etiqueta(date(2026, 1, 7), con_anio=True) == "2026-W02"

    def test_con_dias(self):
        assert etiqueta_con_dias(date(2026, 10, 9)) == "W41 (05/10–11/10)"


class TestBordeDeAnio:
    def test_1_de_enero_de_2027_es_2026_w53(self):
        assert etiqueta(date(2027, 1, 1), con_anio=True) == "2026-W53"

    def test_29_de_diciembre_de_2025_es_2026_w01(self):
        assert etiqueta(date(2025, 12, 29), con_anio=True) == "2026-W01"


class TestRango:
    def test_desde_y_hasta(self):
        s = semana_de(date(2026, 10, 9))
        assert s == Semana(2026, 41)
        assert (s.desde, s.hasta) == (date(2026, 10, 5), date(2026, 10, 11))

    def test_anterior_cruza_el_anio(self):
        assert Semana(2026, 1).anterior() == Semana(2025, 52)
        assert Semana(2027, 1).anterior() == Semana(2026, 53)

    def test_desde_texto(self):
        assert Semana.desde_texto("2026-W41") == Semana(2026, 41)
        with pytest.raises(ValueError):
            Semana.desde_texto("W41")  # sin año es ambigua: no se adivina

    def test_semanas_entre(self):
        assert [str(s) for s in semanas_entre(date(2026, 9, 28), date(2026, 10, 11))] == ["2026-W40", "2026-W41"]


class TestSemanasDelAnio:
    def test_52_o_53(self):
        assert semanas_del_anio(2025) == 52
        assert semanas_del_anio(2026) == 53  # el 31/12/2026 es jueves
        assert semanas_del_anio(2027) == 52

    def test_de_total(self):
        assert Semana(2026, 41).de_total == "W41/53"
