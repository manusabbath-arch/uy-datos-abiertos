"""Tests de `espaciodatos.vigilancia` con dos copias reales tomadas a 31 minutos (2026-11-06)."""

from __future__ import annotations

from datetime import datetime

import pytest

from espaciodatos import cruce, esa, sentry, vigilancia
from espaciodatos.vigilancia import VigilanciaInvalida


@pytest.fixture
def copias(recorte):
    return {
        "jpl_antes": sentry.leer(recorte("vigilancia_sentry_antes.json")),
        "jpl_despues": sentry.leer(recorte("vigilancia_sentry_despues.json")),
        "esa_antes": esa.leer(recorte("vigilancia_esa_antes.txt")),
        "esa_despues": esa.leer(recorte("vigilancia_esa_despues.txt")),
        "retirados": sentry.leer_retirados(recorte("vigilancia_retirados_despues.json")),
    }


def test_sentry_mismos_objetos_dos_cambios(copias):
    j = vigilancia.comparar_sentry(copias["jpl_antes"], copias["jpl_despues"], copias["retirados"])
    assert (j["antes"], j["despues"], j["nuevos"], j["salieron"]) == (4, 4, [], [])
    assert [c["clave"] for c in j["cambios"]] == ["2026 VX1", "2026 UL1"]
    vx1 = j["cambios"][0]["campos"]
    assert vx1["ps_cum"] == (-7.27, -7.05)
    assert vx1["n_imp"] == (18, 11)
    assert vx1["ip"] == (2.731256e-06, 5.965602e-06)


def test_esa_un_nuevo_y_las_dos_horas(copias):
    e = vigilancia.comparar_esa(copias["esa_antes"], copias["esa_despues"])
    assert e["antes_utc"] == datetime(2026, 11, 6, 14, 58) and e["despues_utc"] == datetime(2026, 11, 6, 15, 33)
    assert [f["clave"] for f in e["nuevos"]] == ["2026 VF2"]
    assert e["cambios"][0]["clave"] == "2026 VX1" and e["cambios"][0]["campos"]["ps_cum"] == (-6.72, -9.09)


def test_copias_al_reves_se_rechazan(copias):
    with pytest.raises(VigilanciaInvalida, match="al revés"):
        vigilancia.comparar_esa(copias["esa_despues"], copias["esa_antes"])


def test_direcciones_opuestas(copias):
    j = vigilancia.comparar_sentry(copias["jpl_antes"], copias["jpl_despues"])
    e = vigilancia.comparar_esa(copias["esa_antes"], copias["esa_despues"])
    (op,) = vigilancia.opuestos(j, e)
    assert op["clave"] == "2026 VX1"
    assert op["delta_ps_jpl"] == pytest.approx(0.22) and op["delta_ps_esa"] == pytest.approx(-2.37)


def test_un_objeto_que_sale_dice_si_jpl_lo_retiro(copias):
    despues = [f for f in copias["jpl_despues"] if f["clave"] != "2026 UL1"]
    j = vigilancia.comparar_sentry(copias["jpl_antes"], despues, copias["retirados"])
    (s,) = j["salieron"]
    assert s["clave"] == "2026 UL1" and s["retirado_utc"] is None and s["en_retirados"] is False


def test_un_cambio_de_torino_se_destaca(copias):
    despues = [dict(f) for f in copias["jpl_despues"]]
    despues[0]["torino"] = 1
    j = vigilancia.comparar_sentry(copias["jpl_antes"], despues)
    (t,) = j["torino_cambio"]
    assert t["campos"]["torino"][1] == 1


def test_la_esa_sigue_listando_lo_que_jpl_retiro_hoy(copias):
    c = cruce.comparar(copias["jpl_despues"], copias["esa_despues"], copias["retirados"])
    (x,) = [r for r in c["esa_lista_lo_que_jpl_retiro"] if r["clave"] == "2026 VC3"]
    assert x["retirado_jpl_utc"] == datetime(2026, 11, 6, 15, 29, 58)


def test_informe_markdown(copias):
    j = vigilancia.comparar_sentry(copias["jpl_antes"], copias["jpl_despues"])
    e = vigilancia.comparar_esa(copias["esa_antes"], copias["esa_despues"])
    md = vigilancia.informe(j, e, sellos=["JPL Sentry 2.0 · sha256:bdcad1865d29"])
    assert "**Nuevo** 2026 VF2" in md
    assert "| 2026 VX1 | ESA | -6,72 | -9,09 |" in md
    assert "el Palermo cambió +0,22 en JPL y -2,37 en la ESA" in md
    assert md.rstrip().endswith("sha256:bdcad1865d29")


@pytest.mark.parametrize(
    "x, dec, signo, texto",
    [
        (1594620.3, 0, False, "1.594.620"),
        (-6.72, 2, False, "-6,72"),
        (0.22, 2, True, "+0,22"),
        (0.64, 2, False, "0,64"),
    ],
)
def test_numeros_sin_mezclar_convenciones(x, dec, signo, texto):
    assert vigilancia.numero_es(x, dec, signo=signo) == texto
