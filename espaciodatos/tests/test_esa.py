"""Tests de `espaciodatos.esa` sobre filas reales del 2026-11-06 (sin red, salvo los `red`)."""

from __future__ import annotations

from datetime import datetime

import pytest

from espaciodatos import esa
from espaciodatos.esa import EsaInvalido

ARCHIVO = "esa_recorte.txt"


def _uno(lista, clave):
    (f,) = [x for x in lista["filas"] if x["clave"] == clave]
    return f


def _escribir(tmp_path, texto):
    p = tmp_path / "esa.txt"
    p.write_text(texto, encoding="utf-8")
    return p


def test_lee_la_fecha_y_las_filas(recorte):
    lista = esa.leer(recorte(ARCHIVO))
    assert lista["actualizado_utc"] == datetime(2026, 11, 6, 14, 58)
    assert len(lista["filas"]) == 15
    assert lista["filas"][0]["clave"] == "2008 JL3"


def test_la_designacion_pegada_se_normaliza(recorte):
    f = _uno(esa.leer(recorte(ARCHIVO)), "2008 JL3")
    assert f["objeto"] == "2008JL3"


def test_el_numerado_con_quince_espacios(recorte):
    f = _uno(esa.leer(recorte(ARCHIVO)), "443104")
    assert f["provisional"] == "2013 XK22"


def test_diametro_en_metros_a_km_y_la_marca_de_estimado(recorte):
    lista = esa.leer(recorte(ARCHIVO))
    assert _uno(lista, "2008 JL3")["diametro_km"] == 0.030 and _uno(lista, "2008 JL3")["diametro_estimado"]
    assert not _uno(lista, "2010 UC7")["diametro_estimado"]  # uno de los 9 medidos
    assert _uno(lista, "2025 TV15")["diametro_km"] == pytest.approx(0.0015)


def test_las_dos_ausencias_del_torino_se_conservan(recorte):
    lista = esa.leer(recorte(ARCHIVO))
    a, d = _uno(lista, "2023 TB2"), _uno(lista, "2024 XC")
    assert (a["torino"], a["torino_codigo"]) == (None, "n/a")
    assert (d["torino"], d["torino_codigo"]) == (None, "n/d")


def test_resumen(recorte):
    r = esa.resumen(esa.leer(recorte(ARCHIVO)))
    assert r["numerados"] == 1 and r["diametro_medido"] == 2 and r["anio_max"] <= 2127


def test_encabezado_cambiado_se_rechaza(recorte, tmp_path):
    texto = recorte(ARCHIVO).read_text(encoding="utf-8").replace("PS cum", "PS acc")
    with pytest.raises(EsaInvalido, match="encabezado"):
        esa.leer(_escribir(tmp_path, texto))


def test_fila_sin_el_separador_final_se_rechaza(recorte, tmp_path):
    lineas = recorte(ARCHIVO).read_text(encoding="utf-8").split("\n")
    lineas[4] = lineas[4].rstrip().rstrip("|")
    with pytest.raises(EsaInvalido, match="11 separadores"):
        esa.leer(_escribir(tmp_path, "\n".join(lineas)))


def test_torino_desconocido_se_rechaza(recorte, tmp_path):
    lineas = recorte(ARCHIVO).read_text(encoding="utf-8").split("\n")
    lineas[4] = lineas[4].replace("|  0 |", "| ?? |", 1)
    with pytest.raises(EsaInvalido, match="Torino"):
        esa.leer(_escribir(tmp_path, "\n".join(lineas)))


def test_sin_last_update_se_rechaza(recorte, tmp_path):
    texto = recorte(ARCHIVO).read_text(encoding="utf-8").split("\n", 1)[1]
    with pytest.raises(EsaInvalido, match="Last Update"):
        esa.leer(_escribir(tmp_path, texto))


@pytest.mark.red
def test_red_la_lista_tiene_el_contrato(tmp_path):
    """2.205 objetos el 2026-11-06, horizonte hasta 2127. Se afirma el contrato y el orden de magnitud."""
    lista = esa.leer(esa.descargar(tmp_path / "esa.txt"))
    assert len(lista["filas"]) > 1500
    assert esa.resumen(lista)["anio_max"] <= 2130
