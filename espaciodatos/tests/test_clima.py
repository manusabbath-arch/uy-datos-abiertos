"""Tests de `espaciodatos.clima` con los archivos reales de NOAA SWPC del 2026-11-06 16:32 UTC."""

from __future__ import annotations

import json
from datetime import date, datetime

import pytest

from espaciodatos import clima
from espaciodatos.clima import ClimaInvalido

AHORA = datetime(2026, 11, 6, 16, 32)


def test_kp_franjas_de_tres_horas_y_tipos(recorte):
    kp = clima.leer_kp(recorte("clima_kp.json"))
    assert len(kp) == 81
    assert [sum(f["tipo"] == t for f in kp) for t in ("observado", "estimado", "pronosticado")] == [61, 3, 17]
    assert kp[0]["inicio_utc"] == datetime(2026, 10, 30) and kp[-1]["fin_utc"] == datetime(2026, 11, 9, 3)


def test_estimado_no_quiere_decir_pasado(recorte):
    kp = clima.leer_kp(recorte("clima_kp.json"))
    estimadas_futuras = [f for f in kp if f["tipo"] == "estimado" and f["inicio_utc"] > AHORA]
    assert [f["inicio_utc"].hour for f in estimadas_futuras] == [18, 21]


def test_la_tormenta_empieza_en_4_67(recorte):
    kp = clima.leer_kp(recorte("clima_kp.json"))
    con_g = [f for f in kp if f["escala_g"] > 0]
    assert len(con_g) == 6
    assert sum(f["kp"] >= 5 for f in con_g) == 3  # el umbral ingenuo pierde la mitad
    assert clima.escala_g(4.67) == 1 and clima.escala_g(4.33) == 0 and clima.escala_g(6.0) == 2


def test_rotulo_de_noaa_que_no_coincide_se_rechaza(recorte, tmp_path):
    d = json.loads(recorte("clima_kp.json").read_text())
    (i,) = [n for n, x in enumerate(d) if x["noaa_scale"] == "G2"]
    d[i]["noaa_scale"] = "G3"
    p = tmp_path / "kp.json"
    p.write_text(json.dumps(d))
    with pytest.raises(ClimaInvalido, match="rotulado 'G3'"):
        clima.leer_kp(p)


def test_franja_faltante_se_rechaza(recorte, tmp_path):
    d = json.loads(recorte("clima_kp.json").read_text())
    del d[10]
    p = tmp_path / "kp.json"
    p.write_text(json.dumps(d))
    with pytest.raises(ClimaInvalido, match="no hay 3 h"):
        clima.leer_kp(p)


def test_kp_que_no_es_un_tercio_se_rechaza(recorte, tmp_path):
    d = json.loads(recorte("clima_kp.json").read_text())
    d[0]["kp"] = 1.5
    p = tmp_path / "kp.json"
    p.write_text(json.dumps(d))
    with pytest.raises(ClimaInvalido, match="tercio"):
        clima.leer_kp(p)


@pytest.mark.parametrize("texto, kp", [("3M", 2.67), ("2Z", 2.0), ("2P", 2.33), ("0Z", 0.0), ("1M", 0.67)])
def test_notacion_en_tercios(texto, kp):
    assert clima.kp_de_notacion(texto) == kp


def test_notacion_rara_se_rechaza():
    with pytest.raises(ClimaInvalido):
        clima.kp_de_notacion("3+")


def test_escalas_la_clave_1_es_hoy(recorte):
    e = clima.leer_escalas(recorte("clima_escalas.json"))
    assert e["ayer"]["fecha"] == date(2026, 11, 5) and e["ayer"]["R"]["escala"] == 1
    assert e["hoy"]["fecha"] == e["pronostico"][0]["fecha"] == date(2026, 11, 6)
    assert [d["fecha"].day for d in e["pronostico"]] == [6, 7, 8]
    p = e["pronostico"][0]
    assert (p["R"]["escala"], p["R"]["MinorProb"], p["R"]["MajorProb"], p["S"]["Prob"], p["G"]["escala"]) == (
        None,
        35,
        10,
        5,
        1,
    )


def test_escalas_con_una_clave_de_mas_se_rechazan(recorte, tmp_path):
    d = json.loads(recorte("clima_escalas.json").read_text())
    d["4"] = d["3"]
    p = tmp_path / "e.json"
    p.write_text(json.dumps(d))
    with pytest.raises(ClimaInvalido, match="claves"):
        clima.leer_escalas(p)


def test_alertas_codigo_del_texto_no_del_producto(recorte):
    a = clima.leer_alertas(recorte("clima_alertas.json"))
    por = {x["producto"]: x for x in a}
    assert por["K04W"]["codigo"] == "WARK04" and por["K04W"]["tipo"] == "aviso"
    assert por["EF3A"]["codigo"] == "ALTEF3" and por["EF3A"]["serie"] == 3768
    assert "\r" not in por["EF3A"]["texto"]
    assert [x["emitido_utc"] for x in a] == sorted(x["emitido_utc"] for x in a)


def test_resumen(recorte):
    r = clima.resumen(
        clima.leer_kp(recorte("clima_kp.json")),
        clima.leer_escalas(recorte("clima_escalas.json")),
        clima.leer_alertas(recorte("clima_alertas.json")),
        ahora=AHORA,
    )
    assert r["kp_max_24h"]["kp"] == 3.67
    assert [f["kp"] for f in r["proximas_tormentas"]] == [4.67, 5.0, 4.67, 5.0]


@pytest.mark.red
def test_red_los_tres_archivos_cumplen_el_contrato(tmp_path):
    """El 2026-11-06: 81 franjas, 5 claves de escalas, 86 mensajes en 30 días. Se afirma el contrato
    (franjas de 3 h, tipos en orden, rótulos G coherentes con el umbral de 4,67), no los valores."""
    rutas = clima.descargar(tmp_path)
    assert len(clima.leer_kp(rutas["kp"])) >= 70
    clima.leer_escalas(rutas["escalas"])
    clima.leer_alertas(rutas["alertas"])
