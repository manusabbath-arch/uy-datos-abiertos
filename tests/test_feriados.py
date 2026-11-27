"""Tests de `uydatos.feriados`: feriados nacionales y días hábiles, sin red.

Los esperados de 2026 y 2027 no salen del módulo: los publica, fecha por fecha, una guía
independiente (Brañas, «Feriados de Uruguay 2026 y 2027», leída el 2026-11-27). Las fechas de Pascua
son las del calendario gregoriano publicado.
"""

from __future__ import annotations

from datetime import date

import pytest

from uydatos import feriados
from uydatos.feriados import del_anio, dias_habiles, feriados_de, observado, pascua


def _por_nombre(anio: int) -> dict[str, list[date]]:
    out: dict[str, list[date]] = {}
    for f in del_anio(anio):
        out.setdefault(f.nombre, []).append(f.fecha)
    return out


@pytest.mark.parametrize(
    "anio,esperado",
    [(2024, date(2024, 3, 31)), (2025, date(2025, 4, 20)), (2026, date(2026, 4, 5)), (2027, date(2027, 3, 28))],
)
def test_pascua(anio, esperado):
    assert pascua(anio) == esperado


class TestCalendarioPublicado:
    def test_2026(self):
        f = _por_nombre(2026)
        assert f["Carnaval (lunes)"] == [date(2026, 2, 16)] and f["Carnaval (martes)"] == [date(2026, 2, 17)]
        assert f["Semana de Turismo"] == [date(2026, 3, 30 + i) if i < 2 else date(2026, 4, i - 1) for i in range(7)]
        assert f["Desembarco de los Treinta y Tres Orientales"] == [date(2026, 4, 19)]  # domingo: queda
        assert f["Batalla de Las Piedras"] == [date(2026, 5, 18)]  # lunes: queda
        assert f["12 de octubre"] == [date(2026, 10, 12)]
        assert f["Día de Reyes"] == [date(2026, 1, 6)]  # martes, pero no se traslada

    def test_2027_los_dos_traslados(self):
        f = _por_nombre(2027)
        assert f["Carnaval (lunes)"] == [date(2027, 2, 8)]
        assert f["Semana de Turismo"][0] == date(2027, 3, 22) and f["Semana de Turismo"][-1] == date(2027, 3, 28)
        assert f["Desembarco de los Treinta y Tres Orientales"] == [date(2027, 4, 19)]
        assert f["Batalla de Las Piedras"] == [date(2027, 5, 17)]  # martes 18 -> lunes 17
        assert f["12 de octubre"] == [date(2027, 10, 11)]  # martes 12 -> lunes 11
        assert f["Día de los Difuntos"] == [date(2027, 11, 2)]  # martes, exceptuado: queda
        assert f["Declaratoria de la Independencia"] == [date(2027, 8, 25)]  # miércoles, exceptuado


class TestTraslado:
    @pytest.mark.parametrize(
        "cae,se_observa",
        [
            (date(2027, 5, 18), date(2027, 5, 17)),  # martes -> lunes anterior
            (date(2022, 5, 18), date(2022, 5, 16)),  # miércoles -> lunes anterior
            (date(2023, 10, 12), date(2023, 10, 16)),  # jueves -> lunes siguiente
            (date(2029, 10, 12), date(2029, 10, 15)),  # viernes -> lunes siguiente
            (date(2026, 4, 19), date(2026, 4, 19)),  # domingo -> queda
            (date(2025, 4, 19), date(2025, 4, 19)),  # sábado -> queda
            (date(2026, 5, 18), date(2026, 5, 18)),  # lunes -> queda
        ],
    )
    def test_regla_de_la_ley_16805(self, cae, se_observa):
        assert observado(cae) == se_observa

    def test_solo_tres_se_trasladan(self):
        for anio in range(2002, 2040):
            movidos = {f.nombre for f in del_anio(anio) if f.trasladado}
            assert movidos <= {"Desembarco de los Treinta y Tres Orientales", "Batalla de Las Piedras", "12 de octubre"}

    def test_el_trasladado_conserva_su_fecha_original(self):
        (piedras,) = [f for f in del_anio(2027) if f.nombre == "Batalla de Las Piedras"]
        assert piedras.fecha_original == date(2027, 5, 18) and piedras.trasladado


class TestTipos:
    def test_los_cinco_pagos(self):
        pagos = {(f.fecha.month, f.fecha.day) for f in del_anio(2026) if f.tipo == "pago"}
        assert pagos == {(1, 1), (5, 1), (7, 18), (8, 25), (12, 25)}

    def test_transmision_de_mando_cada_cinco_anios(self):
        for anio, hay in [(2025, True), (2030, True), (2026, False), (2029, False)]:
            fs = feriados_de(date(anio, 3, 1))
            assert any(f.tipo == "no_laborable" for f in fs) is hay, anio


def test_dos_feriados_el_mismo_dia():
    """2025: el 19 de abril cayó sábado, dentro de la Semana de Turismo (del 14 al 20)."""
    nombres = {f.nombre for f in feriados_de(date(2025, 4, 19))}
    assert nombres == {"Semana de Turismo", "Desembarco de los Treinta y Tres Orientales"}


def test_un_dia_comun_no_es_feriado():
    assert feriados_de(date(2026, 11, 27)) == []


class TestDiasHabiles:
    def test_semana_de_turismo_2026(self):
        r = dias_habiles(date(2026, 3, 30), date(2026, 4, 5))
        assert (r.dias, r.lunes_a_viernes, r.sin_ningun_feriado, r.sin_feriados_pagos) == (7, 5, 0, 5)

    def test_mayo_2027_con_el_traslado(self):
        # 21 días de lunes a viernes; el 1 de mayo es sábado; Las Piedras se observa el lunes 17.
        r = dias_habiles(date(2027, 5, 1), date(2027, 5, 31))
        assert r.lunes_a_viernes == 21
        assert r.sin_ningun_feriado == 20
        assert r.sin_feriados_pagos == 21
        assert [f.fecha for f in r.feriados_en_dias_de_semana] == [date(2027, 5, 17)]

    def test_cruza_de_anio(self):
        r = dias_habiles(date(2026, 12, 24), date(2027, 1, 7))
        # 25/12/2026 viernes (pago), 1/1/2027 viernes (pago), 6/1/2027 miércoles (laborable)
        assert r.lunes_a_viernes == 11
        assert r.sin_feriados_pagos == 9
        assert r.sin_ningun_feriado == 8

    def test_rango_al_reves_se_rechaza(self):
        with pytest.raises(ValueError, match="posterior"):
            dias_habiles(date(2026, 2, 1), date(2026, 1, 1))


class TestRechazos:
    def test_antes_de_la_ley_17414(self):
        with pytest.raises(ValueError, match="16.805"):
            del_anio(2001)

    def test_anio_que_no_es_entero(self):
        with pytest.raises(ValueError):
            del_anio("2026")  # type: ignore[arg-type]

    def test_minimo_declarado(self):
        assert feriados.ANIO_MINIMO == 2002
        assert del_anio(2002)
