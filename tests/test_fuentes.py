"""Pruebas contra las fuentes reales. **Salen a internet**: no corren por defecto.

    pytest -m red

Sirven para enterarse de que una fuente cambió de forma (otra URL, otro formato, otra moneda),
no para validar la lógica: eso lo hacen los demás tests, sin red.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from uydatos import ancap, bcu, ibge, indec, inumet, salto_grande
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


def test_inumet_los_seis_datasets_declaran_un_solo_csv():
    """Si un dataset cambia de nombre, o sube un segundo archivo de datos, `descargar()` deja de
    poder elegir cuál es el bueno: mejor enterarse acá y no en la corrida de alguien."""
    for nombre, (dataset, _, _) in inumet.DATASETS.items():
        nombres = [Path(r["url"].split("?")[0]).name for r in recursos(dataset)]
        assert len([n for n in nombres if n.startswith("inumet_")]) == 1, f"{nombre}: {nombres}"


def test_inumet_temperatura_contrato(tmp_path):
    """El archivo completo de temperatura, con su trampa adentro.

    Medido el 09/10/26: 332.070 valores y **una fila cuyo `estacion_id` es el texto de un error
    del servidor**. Si el lector empieza a devolver una octava estación, la fuente cambió: hay
    que mirarla antes de creerle.
    """
    ruta = inumet.descargar("temperatura", tmp_path / "inumet_temperatura.csv")
    serie = inumet.leer_archivo(ruta, inumet.DATASETS["temperatura"][1])
    assert len(serie) > 300_000
    assert {f["estacion"] for f in serie} <= set(inumet.ESTACIONES)
    assert serie[0]["fecha"] < serie[-1]["fecha"]


def test_ideuy_edificio_publico_calle_inexistente_y_esquina():
    import time

    from uydatos import ideuy

    r = ideuy.geocodificar("Avenida 18 de Julio 1360", "Montevideo", "Montevideo")  # Intendencia de Montevideo
    assert r["calidad"] == "puerta_exacta" and r["dentro_de_uruguay"]
    time.sleep(1)
    assert ideuy.geocodificar("Calle que no existe 123", "Montevideo", "Montevideo")["calidad"] == "calle_distinta"
    time.sleep(1)
    assert ideuy.geocodificar("18 de Julio y Ejido", "Montevideo", "Montevideo")["calidad"] in (
        "esquina",
        "calle_sin_numero",
    )
