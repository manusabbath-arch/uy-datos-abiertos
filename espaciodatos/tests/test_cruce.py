"""Tests de `espaciodatos.cruce` y `espaciodatos.designacion` con los recortes reales."""

from __future__ import annotations

import pytest

from espaciodatos import cruce, designacion, esa, sentry
from espaciodatos.designacion import DesignacionInvalida


@pytest.fixture
def listas(recorte):
    return (
        sentry.leer(recorte("sentry_recorte.json")),
        esa.leer(recorte("esa_recorte.txt")),
        sentry.leer_retirados(recorte("sentry_retirados_recorte.json")),
    )


@pytest.mark.parametrize(
    "texto, clave",
    [
        ("2008 JL3", "2008 JL3"),
        ("2008JL3", "2008 JL3"),
        ("(2014 SC324)", "2014 SC324"),
        ("       (2014 SC324)", "2014 SC324"),
        ("443104               2013XK22", "443104"),
        ("443104 (2013 XK22)", "443104"),
        ("101955 Bennu (1999 RQ36)", "101955"),
        ("99942", "99942"),
        ("6344 P-L", "6344 P-L"),
        ("P/2005 JQ5", "P/2005 JQ5"),
    ],
)
def test_una_clave_para_cuatro_formas(texto, clave):
    assert designacion.clave(texto) == clave


@pytest.mark.parametrize("texto", ["2008 jl3", "Apophis", "6344 X-Y", ""])
def test_lo_que_no_tiene_forma_se_rechaza(texto):
    with pytest.raises(DesignacionInvalida):
        designacion.clave(texto)


def test_provisional_de_un_numerado():
    assert designacion.provisional("367943 Duende (2012 DA14)") == "2012 DA14"
    assert designacion.provisional("P/2005 JQ5") is None


def test_el_primero_de_cada_lista_es_otro(listas):
    c = cruce.comparar(*listas)
    assert c["primero_jpl"] == "29075" and c["primero_esa"] == "2008 JL3"


def test_fuera_del_horizonte_no_es_desacuerdo(listas):
    c = cruce.comparar(*listas)
    solo = {x["clave"]: x for x in c["solo_jpl"]}
    assert solo["29075"]["fuera_del_horizonte_esa"] and solo["101955"]["fuera_del_horizonte_esa"]
    assert not solo["367943"]["fuera_del_horizonte_esa"]  # Duende 2116-2122: dentro, y la ESA no lo lista


def test_la_esa_lista_lo_que_jpl_retiro(listas):
    c = cruce.comparar(*listas)
    retirados = {x["clave"]: x for x in c["esa_lista_lo_que_jpl_retiro"]}
    assert set(retirados) == {"2014 ML67", "2023 XJ2", "2016 JT38"}
    assert retirados["2014 ML67"]["ps_esa"] == -3.81


def test_el_numerado_se_empareja(listas):
    c = cruce.comparar(*listas)
    assert "443104" not in {x["clave"] for x in c["solo_jpl"]} | {x["clave"] for x in c["solo_esa"]}


def test_diferencias_de_palermo(listas):
    c = cruce.comparar(*listas)
    d = {x["clave"]: x for x in c["diferencias_ps"]}
    assert d["2010 VQ"]["ps_jpl"] == -4.41 and d["2010 VQ"]["ps_esa"] == -9.21
    assert c["diferencias_ps"][0]["clave"] == "2026 TU8"  # la mayor diferencia medida, casi 5 órdenes
