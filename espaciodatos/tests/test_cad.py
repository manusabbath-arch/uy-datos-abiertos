"""Tests de `espaciodatos.cad` sobre filas reales del 2026-11-06 (sin red, salvo los `red`)."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from espaciodatos import cad
from espaciodatos._jpl import JplInvalido
from espaciodatos.cad import CadInvalido

ARCHIVO = "cad_recorte.json"


def _por_des(filas, des):
    return [f for f in filas if f["des"] == des]


def test_lee_tipa_y_ordena_por_jd(recorte):
    filas = cad.leer(recorte(ARCHIVO))
    assert len(filas) == 11
    jd = [f["jd_tdb"] for f in filas]
    assert jd == sorted(jd)
    assert filas[0]["instante_tdb"] == datetime(1900, 1, 4, 22, 25)
    assert isinstance(filas[0]["dist_au"], float)


def test_cd_como_texto_no_ordena(recorte):
    # El mínimo como string de las 52.247 filas es "1900-Apr-03"; el primero real es del 4 de enero.
    assert "1900-Apr-03 19:19" < "1900-Jan-04 22:25"
    assert cad.instante_tdb("1900-Apr-03 19:19") > cad.instante_tdb("1900-Jan-04 22:25")


def test_meses_sin_locale():
    assert cad.instante_tdb("2029-Apr-13 21:46") == datetime(2029, 4, 13, 21, 46)
    with pytest.raises(CadInvalido):
        cad.instante_tdb("2029-Abr-13 21:46")


def test_apophis_2029_a_una_decima_de_distancia_lunar(recorte):
    a = [f for f in _por_des(cad.leer(recorte(ARCHIVO)), "99942") if f["instante_tdb"].year == 2029][0]
    assert a["nombre"] == "99942 Apophis (2004 MN4)"
    assert a["dist_au"] == pytest.approx(0.000254090910419299)
    assert a["dist_ld"] == pytest.approx(0.0989, abs=1e-3)
    assert a["dist_km"] == pytest.approx(38_011, abs=5)
    assert (a["t_sigma_min"], a["t_sigma_es_cota"]) == (1, True)


@pytest.mark.parametrize(
    "texto, esperado",
    [("< 00:01", (1, True)), ("13:02", (782, False)), ("2_09:08", (3428, False)), ("9_17:20", (14_000, False))],
)
def test_los_tres_formatos_de_t_sigma(texto, esperado):
    assert cad.t_sigma_minutos(texto) == esperado


def test_t_sigma_desconocido_se_rechaza():
    with pytest.raises(CadInvalido, match="tres formatos"):
        cad.t_sigma_minutos("2d 09:08")


def test_el_cometa_no_tiene_h_y_se_marca(recorte):
    (c,) = _por_des(cad.leer(recorte(ARCHIVO)), "289P")
    assert c["h"] is None and c["cometa"] and c["nombre"] == "289P/Blanpain"


def test_h_nulo_en_un_asteroide_se_rechaza(modificado):
    def sin_h(d):
        d["data"][0][d["fields"].index("h")] = None  # 509352 (2007 AG), no es cometa

    with pytest.raises(CadInvalido, match="sólo los cometas"):
        cad.leer(modificado(ARCHIVO, sin_h))


def test_v_inf_nulo_se_marca_y_no_se_rellena(recorte):
    # 2020 CD3 el 2019-04-04, en plena captura: v_inf nulo. Medido también nulo en 2044 y 2061.
    (m,) = _por_des(cad.leer(recorte(ARCHIVO)), "2020 CD3")
    assert m["v_inf_kms"] is None and m["sin_v_inf"]


def test_dist_min_cero_se_marca_y_no_es_impacto(recorte):
    filas = cad.leer(recorte(ARCHIVO))
    (h,) = _por_des(filas, "2012 HA34")
    # Un objeto descubierto en 2012 "pasó" en 1945 con el mínimo 3σ recortado en cero: cálculo, no observación
    assert h["instante_tdb"].year == 1945 and h["dist_min_en_cero"] and h["dist_au"] > 0.01


def test_diametro_nulo_se_queda_nulo(recorte):
    filas = cad.leer(recorte(ARCHIVO))
    assert _por_des(filas, "2014 SC324")[0]["diametro_km"] is None
    (d,) = _por_des(filas, "8014")  # el diámetro medido sin su sigma: 1 en 52.247
    assert d["diametro_km"] == 0.7 and d["diametro_sigma_km"] is None


def test_fullname_sin_los_espacios_de_alineacion(recorte):
    assert _por_des(cad.leer(recorte(ARCHIVO)), "2014 SC324")[0]["nombre"] == "(2014 SC324)"


def test_distancias_desordenadas_se_rechazan(modificado):
    def invertir(d):
        i, j = d["fields"].index("dist_min"), d["fields"].index("dist_max")
        d["data"][0][i], d["data"][0][j] = d["data"][0][j], d["data"][0][i]

    with pytest.raises(CadInvalido, match="dist_min <= dist <= dist_max"):
        cad.leer(modificado(ARCHIVO, invertir))


def test_un_campo_nuevo_se_rechaza_aunque_la_version_sea_la_misma(modificado):
    def agregar(d):
        d["fields"].append("body")
        for f in d["data"]:
            f.append("Earth")

    with pytest.raises(JplInvalido, match="cambió el formato"):
        cad.leer(modificado(ARCHIVO, agregar))


def test_version_menor_distinta_se_acepta_y_mayor_se_rechaza(modificado):
    def menor(d):
        d["signature"]["version"] = "1.6"

    def mayor(d):
        d["signature"]["version"] = "2.0"

    assert len(cad.leer(modificado(ARCHIVO, menor))) == 11
    with pytest.raises(JplInvalido, match="versión mayor"):
        cad.leer(modificado(ARCHIVO, mayor))


def test_count_que_no_coincide_se_rechaza(modificado):
    def cortar(d):
        d["data"].pop()

    with pytest.raises(JplInvalido, match="count dice 11 y vinieron 10"):
        cad.leer(modificado(ARCHIVO, cortar))


def test_respuesta_vacia_sin_fields(tmp_path):
    p = tmp_path / "vacio.json"
    p.write_text('{"count":0,"signature":{"source":"NASA/JPL SBDB Close Approach Data API","version":"1.5"}}')
    assert cad.leer(p) == []


def test_url_con_fechas_explicitas():
    u = cad.url(date(2026, 1, 1), date(2027, 1, 1))
    assert "date-min=2026-01-01" in u and "fullname=true" in u and "diameter=true" in u
    with pytest.raises(CadInvalido):
        cad.url(date(2027, 1, 1), date(2026, 1, 1))


def test_resumen_y_proximos(recorte):
    filas = cad.leer(recorte(ARCHIVO))
    r = cad.resumen(filas, ahora=datetime(2026, 11, 6, 15, 0))
    assert r["filas"] == 11 and r["cometas"] == 1 and r["dist_min_en_cero"] == 2
    assert r["mas_cercano_futuro"]["des"] == "99942"
    prox = cad.proximos(filas, desde=datetime(2026, 11, 6), dias=30)
    assert [f["des"] for f in prox] == ["2026 VN1", "2023 VE6"]


def test_sello_lleva_la_version(recorte):
    s = cad.sello(recorte(ARCHIVO), filas=11)
    assert s["fuente"] == "JPL CAD 1.5" and len(s["sha256"]) == 64


@pytest.mark.red
def test_red_apophis_sigue_a_0_000254_au_el_13_de_abril_de_2029(tmp_path):
    """El número medido el 2026-11-06: 0,000254090910419299 au el 2029-Apr-13 21:46 TDB.

    Con una órbita tan observada, este número no debería moverse más allá de la sexta cifra;
    si se mueve, la órbita cambió y se anota."""
    p = cad.descargar(tmp_path / "cad.json", date(2029, 4, 1), date(2029, 5, 1), dist_max_au=0.001)
    (a,) = [f for f in cad.leer(p) if f["des"] == "99942"]
    assert a["dist_au"] == pytest.approx(0.000254090910419299, rel=1e-4)
    assert a["instante_tdb"] == datetime(2029, 4, 13, 21, 46)


@pytest.mark.red
def test_red_el_historico_1900_1910_tiene_el_contrato(tmp_path):
    """1900-1910 a 0,05 au: el contrato de campos y el orden se cumplen en el pasado calculado."""
    filas = cad.leer(cad.descargar(tmp_path / "cad.json", date(1900, 1, 1), date(1910, 1, 1)))
    assert len(filas) > 50
