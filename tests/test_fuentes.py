"""Pruebas contra las fuentes reales. **Salen a internet**: no corren por defecto.

    pytest -m red

Sirven para enterarse de que una fuente cambió de forma (otra URL, otro formato, otra moneda),
no para validar la lógica: eso lo hacen los demás tests, sin red.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from uydatos import ancap, bcu, catalogo, ibge, indec, inumet, mides, salto_grande
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


@pytest.mark.red
def test_buscar_por_organizacion_mides():
    """Medido el 2026-10-09: 1.875. Se afirma un piso y no el número exacto: un dataset nuevo del MIDES
    no es un error, y un test semanal que falla por eso enseña a ignorarlo."""
    assert catalogo.buscar("", organizacion="mides")["total"] >= 1500


@pytest.mark.red
def test_el_datastore_de_inumet_se_puede_consultar_sin_bajar_el_archivo():
    """Medido el 2026-10-09: `total` 332.071 e incluye la fila del encabezado."""
    r = catalogo.datastore_search("f800fc53-556b-4d1c-8bd6-28b41f9cf146", limite=2)
    assert r["total"] == 332071
    assert "temp_aire" in r["campos"]


def test_la_familia_de_mides_tiene_mil_ochocientos_sesenta_y_nueve_indicadores():
    """Medido el 2026-10-09: la organizacion declara 1.875 datasets y 1.869 son de la familia."""
    r = mides.indicadores(filas=100)
    assert r["total"] == 1875
    assert all(d["nombre"].startswith("mides-indicador-") for d in r["indicadores"])


def test_un_indicador_de_mides_se_baja_y_se_lee(tmp_path):
    """Medido el 2026-10-09: el 10745 tiene dos filas y sus columnas son `año, valor`."""
    ruta = mides.descargar("10745", tmp_path / "mides-10745.csv")
    s = mides.resumen(ruta)
    assert s["columnas"] == ["año", "valor"]
    assert s["filas"] == 2
    assert s["filas_en_blanco"] == 0


def test_salto_grande_lecturas_de_la_estacion_salto(tmp_path):
    from datetime import date

    ruta = salto_grande.descargar_datos("A501258E", date(2026, 9, 1), date(2026, 9, 2), tmp_path / "s.xml")
    lecturas = salto_grande.leer_datos(ruta)
    assert 90 <= len(lecturas) <= 97
    assert all(f["H"] is not None and 0 < f["H"] < 20 for f in lecturas)
