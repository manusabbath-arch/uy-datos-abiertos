"""Pruebas contra las fuentes reales. **Salen a internet**: no corren por defecto.

    pytest -m red

Sirven para enterarse de que una fuente cambió de forma (otra URL, otro formato, otra moneda),
no para validar la lógica: eso lo hacen los demás tests, sin red.
"""

from __future__ import annotations

import pytest

from uydatos import ancap, bcu, ibge, indec, salto_grande
from uydatos.catalogo import recursos

pytestmark = pytest.mark.red


def test_bcu_dolar_de_un_mes_cerrado(tmp_path):
    (p,) = bcu.descargar(2225, "2026-01", "2026-01", tmp_path)
    serie = bcu.leer_crudo(p, 2225)
    assert 15 <= len(serie) <= 23
    assert all(30 < v < 60 for v in serie.values())


def test_indec_serie_viva(tmp_path):
    serie = indec.leer(indec.descargar(tmp_path / "ipc.json"))
    assert serie[0] == {"periodo": "2016-12", "valor": pytest.approx(100.0)}


def test_ibge_ipca(tmp_path):
    serie = ibge.leer(ibge.descargar(tmp_path / "ipca.json"))
    assert next(s["valor"] for s in serie if s["periodo"] == "1993-12") == 100


def test_salto_grande_lista(tmp_path):
    estaciones = salto_grande.leer_estaciones(salto_grande.descargar_lista(tmp_path / "e.xml"))
    assert len(estaciones) > 10


def test_ancap_csv(tmp_path):
    serie = ancap.serie_mensual(ancap.leer_publicaciones(ancap.descargar(tmp_path / "a.csv")))
    assert any(s["precio"] for s in serie)


def test_catalogo_inia_tiene_csv_anuales():
    assert any("ppt_tmax_tmin_sg_" in r["url"] for r in recursos("inia-precipitacion-temps-extremas-sg"))
