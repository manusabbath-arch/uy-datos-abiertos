"""Tests de `espaciodatos.bolidos` sobre filas reales del 2026-11-06 (sin red, salvo los `red`)."""

from __future__ import annotations

from datetime import datetime

import pytest

from espaciodatos import bolidos
from espaciodatos.bolidos import BolidoInvalido

ARCHIVO = "bolidos_recorte.json"
CENTRO_UY = (-32.5, -56.0)


def test_ordena_ascendente_aunque_el_api_venga_descendente(recorte):
    filas = bolidos.leer(recorte(ARCHIVO))
    assert filas[0]["instante_utc"] == datetime(2008, 4, 7, 1, 2, 28)
    assert filas[-1]["instante_utc"] == datetime(2026, 10, 4, 3, 14, 45)


def test_el_hemisferio_da_el_signo(recorte):
    (uy,) = [b for b in bolidos.leer(recorte(ARCHIVO)) if b["instante_utc"].year == 2008]
    assert (uy["lat"], uy["lon"]) == (-31.8, -58.5)
    assert uy["energia_impacto_kt"] == 0.076


def test_el_unico_bolido_de_uruguay(recorte):
    # Caja de Uruguay: 1 real. Sin la dirección (todo S/W) serían 4 en el archivo completo.
    filas = bolidos.leer(recorte(ARCHIVO))
    caja = [b for b in filas if b["lat"] is not None and -36 < b["lat"] < -29 and -60 < b["lon"] < -52]
    assert [b["instante_utc"].date().isoformat() for b in caja] == ["2008-04-07"]
    cercanos = bolidos.cerca(filas, *CENTRO_UY, 600)
    assert [round(b["distancia_km"]) for b in cercanos] == [248, 394, 516]


def test_sin_ubicacion_no_cuenta_como_lejano(recorte):
    filas = bolidos.leer(recorte(ARCHIVO))
    assert sum(b["lat"] is None for b in filas) == 1
    assert all(b["lat"] is not None for b in bolidos.cerca(filas, 0, 0, 20_000))


def test_chelyabinsk_es_el_mayor(recorte):
    r = bolidos.resumen(bolidos.leer(recorte(ARCHIVO)))
    assert r["mayor"]["instante_utc"] == datetime(2013, 2, 15, 3, 20, 26) and r["mayor"]["energia_impacto_kt"] == 441.0


def test_ubicacion_a_medias_se_rechaza(modificado):
    def media(d):
        d["data"][0][d["fields"].index("lon-dir")] = None

    with pytest.raises(BolidoInvalido, match="a medias"):
        bolidos.leer(modificado(ARCHIVO, media))


def test_un_valor_con_signo_se_rechaza(modificado):
    # Si el API empezara a mandar el signo y siguiera mandando la dirección, se invertiría dos veces.
    def signo(d):
        i = d["fields"].index("lat")
        d["data"][0][i] = "-" + d["data"][0][i]

    with pytest.raises(BolidoInvalido, match="con signo"):
        bolidos.leer(modificado(ARCHIVO, signo))


def test_direccion_desconocida_se_rechaza(modificado):
    def dir_mala(d):
        d["data"][0][d["fields"].index("lat-dir")] = "s"

    with pytest.raises(BolidoInvalido, match="se esperaba S o N"):
        bolidos.leer(modificado(ARCHIVO, dir_mala))


def test_distancia_haversine():
    # Montevideo a Buenos Aires, ~200 km
    assert bolidos.distancia_km(-34.90, -56.16, -34.60, -58.38) == pytest.approx(205, abs=5)


@pytest.mark.red
def test_red_el_bolido_de_2008_sigue_siendo_el_unico_de_uruguay(tmp_path):
    """1.074 bólidos el 2026-11-06, y uno solo en la caja de Uruguay (2008-04-07). Si aparece otro,
    no es un error: es un dato nuevo, y se anota con su fecha."""
    filas = bolidos.leer(bolidos.descargar(tmp_path / "b.json"))
    assert len(filas) >= 1074
    caja = [b for b in filas if b["lat"] is not None and -36 < b["lat"] < -29 and -60 < b["lon"] < -52]
    assert caja[0]["instante_utc"] == datetime(2008, 4, 7, 1, 2, 28)
