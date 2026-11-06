"""Tests de `espaciodatos.herramientas`: la forma de la respuesta y lo que dice, con el reloj fijo."""

from __future__ import annotations

import json
import shutil
from datetime import datetime

import pytest

from espaciodatos import _jpl, clima, herramientas

AHORA = datetime(2026, 11, 6, 16, 32)
COPIAS = {
    "cad_recorte.json": "cad.json",
    "sentry_recorte.json": "sentry.json",
    "sentry_retirados_recorte.json": "sentry_retirados.json",
    "esa_recorte.txt": "esa_riesgo.txt",
    "bolidos_recorte.json": "bolidos.json",
    "clima_kp.json": "clima_kp.json",
    "clima_escalas.json": "clima_escalas.json",
    "clima_alertas.json": "clima_alertas.json",
}


@pytest.fixture
def carpeta(tmp_path, recorte, monkeypatch):
    for origen, destino in COPIAS.items():
        shutil.copy(recorte(origen), tmp_path / destino)
    monkeypatch.setattr(_jpl, "ahora_utc", lambda: AHORA)
    monkeypatch.setattr(clima, "ahora_utc", lambda: AHORA)
    return tmp_path


def _forma(r):
    assert set(r) == {"datos", "advertencias", "procedencia"}
    json.dumps(r)  # serializable tal cual
    assert all(len(s["sha256"]) == 64 for s in r["procedencia"])


@pytest.mark.parametrize("nombre", sorted(herramientas.HERRAMIENTAS))
def test_todas_devuelven_la_misma_forma(carpeta, nombre):
    kwargs = {"objeto": "2008 JL3"} if nombre == "estado_de_un_objeto" else {}
    _forma(herramientas.HERRAMIENTAS[nombre]["funcion"](carpeta, **kwargs))


def test_el_registro_describe_parametros():
    h = herramientas.HERRAMIENTAS["estado_de_un_objeto"]
    assert h["parametros"] == {"objeto": "requerido"}
    assert h["descripcion"].startswith("Todo lo que las copias dicen de un objeto")
    assert herramientas.HERRAMIENTAS["bolidos_cerca"]["parametros"]["radio_km"] == "opcional, por defecto 600.0"


def test_proximos_acercamientos(carpeta):
    r = herramientas.proximos_acercamientos(carpeta, dias=30, max_ld=50)
    assert [x["des"] for x in r["datos"]] == ["2023 VE6"]  # 2026 VN1 ya pasó (06/11 06:55)
    assert r["advertencias"][0] == herramientas.AVISO_TDB


def test_estado_de_un_objeto_que_jpl_retiro_y_la_esa_lista(carpeta):
    r = herramientas.estado_de_un_objeto(carpeta, "2014ML67")
    d = r["datos"]
    assert (
        d["jpl"] is None and d["jpl_retirado_utc"] == "2021-08-09T16:58:35" and d["esa"]["palermo_acumulado"] == -3.81
    )
    assert any("las agencias no coinciden" in a for a in r["advertencias"])


def test_estado_acepta_un_numerado_como_entero(carpeta):
    r = herramientas.estado_de_un_objeto(carpeta, 99942)
    assert r["datos"]["jpl_retirado_utc"] == "2021-02-21T08:22:28"
    assert r["datos"]["acercamientos_futuros"][0]["instante_tdb"] == "2029-04-13T21:46:00"


def test_estado_con_torino_nulo_avisa(carpeta):
    r = herramientas.estado_de_un_objeto(carpeta, "29075")
    assert r["datos"]["jpl"]["torino"] is None and herramientas.AVISO_TORINO in r["advertencias"]


def test_desacuerdos(carpeta):
    d = herramientas.desacuerdos_entre_agencias(carpeta)["datos"]
    assert d["primero_jpl"] == "29075" and d["primero_esa"] == "2008 JL3"
    assert d["palermo_distinto"]["mayores"][0] == {
        "clave": "2026 TU8",
        "ps_jpl": -7.87,
        "ps_esa": -12.83,
        "diferencia": -4.96,
    }


def test_bolidos_cerca_de_montevideo(carpeta):
    # El bólido de 2008 cayó a ~406 km de Montevideo: 400 km lo deja afuera, 450 lo incluye
    assert herramientas.bolidos_cerca(carpeta, lat=-34.9, lon=-56.2, radio_km=400)["datos"]["bolidos"] == []
    d = herramientas.bolidos_cerca(carpeta, lat=-34.9, lon=-56.2, radio_km=450)["datos"]
    assert [b["instante_utc"][:10] for b in d["bolidos"]] == ["2008-04-07"]
    assert 400 < d["bolidos"][0]["distancia_km"] < 415


def test_clima_espacial(carpeta):
    d = herramientas.clima_espacial(carpeta)["datos"]
    assert d["kp_max_24h"]["kp"] == 3.67 and len(d["proximas_tormentas"]) == 4


def test_falta_un_archivo(tmp_path):
    with pytest.raises(FileNotFoundError, match="actualizar"):
        herramientas.proximos_acercamientos(tmp_path)


def test_llamar_por_nombre(carpeta):
    texto = herramientas.llamar("estado_de_un_objeto", carpeta, objeto="2008 JL3")
    assert json.loads(texto)["datos"]["clave"] == "2008 JL3"
    with pytest.raises(KeyError, match="no es una herramienta"):
        herramientas.llamar("borrar_todo", carpeta)
