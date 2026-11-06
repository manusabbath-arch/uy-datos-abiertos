"""Tests de `espaciodatos.sentry` sobre respuestas reales del 2026-11-06 (sin red, salvo los `red`)."""

from __future__ import annotations

import json
from datetime import date, datetime

import pytest

from espaciodatos import sentry
from espaciodatos.sentry import SentryInvalido

ARCHIVO = "sentry_recorte.json"


def _uno(filas, clave):
    (f,) = [x for x in filas if x["clave"] == clave]
    return f


def test_lee_y_ordena_por_palermo_acumulado(recorte):
    filas = sentry.leer(recorte(ARCHIVO))
    assert len(filas) == 11
    assert [f["clave"] for f in filas[:3]] == ["29075", "101955", "2008 JL3"]
    assert all(a["ps_cum"] >= b["ps_cum"] for a, b in zip(filas, filas[1:]))


def test_torino_nulo_no_es_cero(recorte):
    # Los dos de mayor riesgo tienen el Torino nulo: sus impactos son a más de 100 años (2880, 2178-2290)
    filas = sentry.leer(recorte(ARCHIVO))
    for clave in ("29075", "101955"):
        f = _uno(filas, clave)
        assert f["torino"] is None and not f["torino_definido"]
    assert _uno(filas, "2008 JL3")["torino"] == 0


def test_el_dia_fraccionario_de_bennu(recorte):
    b = _uno(sentry.leer(recorte(ARCHIVO)), "101955")
    assert b["ultima_obs"] == date(2020, 10, 3)
    with pytest.raises(ValueError):
        date.fromisoformat("2020-10-3.80160")  # lo que rompe un lector ingenuo


def test_el_diametro_es_estimado_y_se_dice_en_el_nombre(recorte):
    f = _uno(sentry.leer(recorte(ARCHIVO)), "2015 XO129")
    assert f["diametro_estimado_km"] == 0.031  # CAD lo trae medido en 0,060: el doble
    assert "diametro_km" not in f


def test_n_imp_entero_aunque_la_documentacion_diga_string(recorte, modificado):
    assert isinstance(_uno(sentry.leer(recorte(ARCHIVO)), "2008 JL3")["n_imp"], int)

    def como_string(d):
        for o in d["data"]:
            o["n_imp"] = str(o["n_imp"])

    assert _uno(sentry.leer(modificado(ARCHIVO, como_string)), "2008 JL3")["n_imp"] == 44


def test_count_string(recorte):
    d = json.loads(recorte(ARCHIVO).read_text())
    assert d["count"] == "11"  # string en Sentry, entero en CAD


def test_ps_cum_menor_que_ps_max_se_rechaza(modificado):
    def romper(d):
        d["data"][0]["ps_cum"] = "-9.99"

    with pytest.raises(SentryInvalido, match="acumulada"):
        sentry.leer(modificado(ARCHIVO, romper))


def test_una_clave_nueva_se_rechaza(modificado):
    def agregar(d):
        d["data"][0]["mass"] = "1e9"

    with pytest.raises(SentryInvalido, match="sobran"):
        sentry.leer(modificado(ARCHIVO, agregar))


def test_retirados_con_cometa_y_relevamiento(recorte):
    r = sentry.leer_retirados(recorte("sentry_retirados_recorte.json"))
    claves = {x["clave"] for x in r}
    assert {"6344 P-L", "P/2005 JQ5", "99942", "2024 YR4"} <= claves
    assert "6344" not in claves  # el relevamiento no es el numerado 6344
    yr4 = [x for x in r if x["clave"] == "2024 YR4"][0]
    assert yr4["retirado_utc"] == datetime(2026, 3, 5, 16, 2, 50)


def test_objeto_retirado_responde_200_con_error(recorte):
    d = json.loads(recorte("sentry_objeto_retirado.json").read_text())
    e = sentry.estado_desde_respuesta(d, "99942")
    assert e == {"des": "99942", "estado": "retirado", "retirado_utc": datetime(2021, 2, 21, 8, 22, 28)}


def test_objeto_nunca_listado():
    d = {"signature": {"version": "2.0", "source": "NASA/JPL Sentry Data API"}, "error": "specified object not found"}
    assert sentry.estado_desde_respuesta(d, "433")["estado"] == "nunca"


def test_error_desconocido_se_rechaza():
    d = {"signature": {"version": "2.0", "source": "NASA/JPL Sentry Data API"}, "error": "database busy"}
    with pytest.raises(SentryInvalido, match="ninguno de los medidos"):
        sentry.estado_desde_respuesta(d, "433")


def test_objeto_en_lista(recorte):
    d = json.loads(recorte("sentry_objeto_2008jl3.json").read_text())
    e = sentry.estado_desde_respuesta(d, "2008 JL3")
    assert e["estado"] == "en_lista" and e["n_imp"] == 44 and e["metodo"] == "IOBS" and e["torino"] == 0


@pytest.mark.red
def test_red_la_lista_tiene_el_contrato_y_mas_de_2000_objetos(tmp_path):
    """2.239 objetos el 2026-11-06. La lista se mueve todos los días (2 retirados ese mismo día):
    se afirma el orden de magnitud y el contrato entero, no el número exacto."""
    rutas = sentry.descargar(tmp_path)
    filas = sentry.leer(rutas["sentry"])
    assert len(filas) > 2000
    assert {"29075", "101955"} <= {f["clave"] for f in filas if not f["torino_definido"]}
    assert len(sentry.leer_retirados(rutas["sentry_retirados"])) >= 3596


@pytest.mark.red
def test_red_apophis_sigue_retirado():
    assert sentry.estado("99942")["estado"] == "retirado"
