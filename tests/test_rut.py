"""Tests de `uydatos.rut`: dígito verificador de RUT y cédula, y las trampas de Excel."""

from __future__ import annotations

import pytest

from uydatos.rut import (
    dv_ci,
    dv_rut,
    es_ci_valida,
    es_rut_valido,
    normalizar,
    validar_ci,
    validar_rut,
)


class TestDigitoVerificador:
    def test_dv_rut_contra_el_algoritmo_a_mano(self):
        """`suma = Σ dígito×peso; resto = 11 - (suma % 11)` sobre pesos
        (4,3,2,9,8,7,6,5,4,3,2) — calculado a mano una vez para no depender de
        que `dv_rut` se valide contra sí mismo."""
        assert dv_rut("01234567891") == 9

    def test_dv_ci_contra_el_algoritmo_a_mano(self):
        # pesos (2,9,8,7,6,3,4) sobre "1234567", cada producto mod 10:
        # 2,8,4,8,0,8,8 -> suma 38 -> %10 = 8 -> dv=((8-10)*-1)%10=2
        assert dv_ci("1234567") == 2

    def test_normalizar_convierte_float_sin_correr_digitos(self):
        """El bug documentado: borrar el punto de `12345678919.0` corre los
        dígitos. `normalizar()` tiene que pasar por `int()` antes de rellenar."""
        digitos, motivo = normalizar(12345678919.0, 12)
        assert motivo is None
        assert digitos == "012345678919"

    def test_notacion_cientifica_no_se_repara(self):
        digitos, motivo = normalizar("1.23E+11", 12)
        assert digitos is None
        assert motivo == "notacion_cientifica"

    def test_vacio_es_null_no_cero(self):
        _, motivo = normalizar("", 12)
        assert motivo == "vacio_o_cero"
        _, motivo = normalizar(0, 12)
        assert motivo == "vacio_o_cero"


class TestEstados:
    def test_rut_valido_con_el_dv_calculado(self):
        base = "21000000000"
        rut = base + str(dv_rut(base))
        assert validar_rut(rut) == ("valido", rut)
        assert es_rut_valido(rut)

    def test_rut_con_dv_cambiado_no_valida(self):
        base = "21000000000"
        malo = base + str((dv_rut(base) + 1) % 10)
        assert validar_rut(malo)[0] == "dv_no_valida"
        assert not es_rut_valido(malo)

    def test_rut_con_estructura_rara_se_informa_aparte(self):
        """Posiciones 9-10 distintas de 00: el dv valida, pero se marca."""
        base = "21000000110"
        dv = dv_rut(base)
        if dv < 0:
            pytest.skip("ese prefijo no tiene dv valido")
        assert validar_rut(base + str(dv))[0] == "dv_ok_estructura_rara"

    def test_cedula_con_separadores(self):
        assert validar_ci("1.234.567-2") == ("valido", "12345672")
        assert es_ci_valida("1,234,567-2")

    def test_cedula_con_dv_malo(self):
        assert validar_ci("1.234.567-3")[0] == "dv_no_valida"

    def test_texto_no_numerico(self):
        assert validar_ci("abc")[0] == "no_numerico"
