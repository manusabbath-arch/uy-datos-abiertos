"""Tests de `uydatos.limites`, sin red, con capas sintéticas que tienen la forma de las reales."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from uydatos.limites import (
    CAPAS,
    LimitesInvalido,
    contiene,
    leer,
    mas_cercana,
    ubicar,
)


def _cuadrado(lon0: float, lat0: float, lado: float, agujero: bool = False) -> list:
    exterior = [[lon0, lat0], [lon0 + lado, lat0], [lon0 + lado, lat0 + lado], [lon0, lat0 + lado], [lon0, lat0]]
    anillos = [exterior]
    if agujero:
        m, c = lado / 4, lado / 2
        anillos.append(
            [
                [lon0 + m, lat0 + m],
                [lon0 + c, lat0 + m],
                [lon0 + c, lat0 + c],
                [lon0 + m, lat0 + c],
                [lon0 + m, lat0 + m],
            ]
        )
    return [anillos]


def _departamentos(tmp_path: Path, extra: list | None = None, n: int = 19) -> Path:
    features = []
    for i in range(1, n + 1):
        props = {"depto": i, "nombre": f"DEPTO {i}", "cdepto_iso": f"UY{i:02d}"}
        geom = {"type": "MultiPolygon", "coordinates": _cuadrado(-58.0 + (i - 1) * 0.2, -33.0, 0.2, agujero=i == 1)}
        features.append({"type": "Feature", "properties": props, "geometry": geom})
    features += extra or []
    p = tmp_path / "departamentos.geojson"
    p.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")
    return p


CONTESTADO = {
    "type": "Feature",
    "properties": {"depto": 2, "nombre": "LIMITE CONTESTADO", "cdepto_iso": "UY02"},
    "geometry": {"type": "MultiPolygon", "coordinates": _cuadrado(-56.0, -30.4, 0.2)},
}


def _localidades(tmp_path: Path) -> Path:
    features = [
        {
            "type": "Feature",
            "properties": {
                "DEPTO": 15,
                "CODLOC": 15020,
                "NOMBDEPTO": "SALTO",
                "NOMBLOC": "SALTO",
                "pob_tot_23": 114043,
                "viv_tot_23": 41536,
                "capital": True,
            },
            "geometry": {"type": "Polygon", "coordinates": _cuadrado(-58.0, -31.4, 0.05)[0]},
        },
        {
            "type": "Feature",
            "properties": {
                "DEPTO": 15,
                "CODLOC": 15939,
                "NOMBDEPTO": "SALTO",
                "NOMBLOC": "GARIBALDI",
                "pob_tot_23": 549,
                "viv_tot_23": 185,
                "capital": False,
            },
            "geometry": {"type": "MultiPolygon", "coordinates": _cuadrado(-57.5, -31.2, 0.01)},
        },
    ]
    p = tmp_path / "localidades.geojson"
    p.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")
    return p


class TestDepartamentos:
    def test_lee_los_19(self, tmp_path):
        areas = leer("departamentos", _departamentos(tmp_path))
        assert len(areas) == 19
        assert areas[0]["nombre"] == "DEPTO 1" and areas[0]["codigo"] == 1

    def test_el_limite_contestado_no_es_un_departamento(self, tmp_path):
        """Medido el 10/10/2026: la capa del INE trae 20 polígonos; el vigésimo es 'LIMITE CONTESTADO'."""
        areas = leer("departamentos", _departamentos(tmp_path, [CONTESTADO]))
        assert len(areas) == 20
        contestado = [a for a in areas if a["tipo"] == "limite_contestado"]
        assert [a["nombre"] for a in contestado] == ["LIMITE CONTESTADO"]
        # El INE le pone el código y el ISO de Artigas: el departamento al que lo asigna.
        assert contestado[0]["codigo"] == 2 and contestado[0]["departamento"] == "DEPTO 2"
        assert sum(1 for a in areas if a["tipo"] == "departamento") == 19

    def test_un_codigo_repetido_entre_departamentos_se_rechaza(self, tmp_path):
        p = _departamentos(tmp_path)
        d = json.loads(p.read_text(encoding="utf-8"))
        d["features"][3]["properties"]["depto"] = 1
        p.write_text(json.dumps(d), encoding="utf-8")
        with pytest.raises(LimitesInvalido, match="repetido"):
            leer("departamentos", p)

    def test_faltan_departamentos(self, tmp_path):
        with pytest.raises(LimitesInvalido, match="19"):
            leer("departamentos", _departamentos(tmp_path, n=18))

    def test_coordenadas_en_metros_se_rechazan(self, tmp_path):
        """Sin srsName=EPSG:4326 el servicio devuelve UTM 21S (metros): un punto en grados nunca cae adentro."""
        p = _departamentos(tmp_path)
        d = json.loads(p.read_text(encoding="utf-8"))
        d["features"][0]["geometry"]["coordinates"] = [
            [[[580000.0, 6140000.0], [581000.0, 6140000.0], [580000.0, 6141000.0], [580000.0, 6140000.0]]]
        ]
        p.write_text(json.dumps(d), encoding="utf-8")
        with pytest.raises(LimitesInvalido, match="metros|4326"):
            leer("departamentos", p)

    def test_no_es_geojson(self, tmp_path):
        p = tmp_path / "x.geojson"
        p.write_text("<ServiceExceptionReport>error</ServiceExceptionReport>", encoding="utf-8")
        with pytest.raises(LimitesInvalido):
            leer("departamentos", p)


class TestUbicar:
    def test_un_punto_adentro(self, tmp_path):
        areas = leer("departamentos", _departamentos(tmp_path))
        assert ubicar(areas, -32.9, -57.7)["nombre"] == "DEPTO 2"

    def test_un_punto_en_un_agujero_no_esta_adentro(self, tmp_path):
        areas = leer("departamentos", _departamentos(tmp_path))
        depto1 = areas[0]
        assert contiene(depto1, -32.99, -57.99)
        assert not contiene(depto1, -32.93, -57.93)  # dentro del agujero

    def test_un_punto_fuera_de_todo_es_none(self, tmp_path):
        areas = leer("departamentos", _departamentos(tmp_path))
        assert ubicar(areas, -36.5, -54.0) is None  # en el mar

    def test_el_departamento_ignora_el_limite_contestado(self, tmp_path):
        areas = leer("departamentos", _departamentos(tmp_path, [CONTESTADO]))
        r = ubicar(areas, -30.3, -55.9)
        assert r is not None and r["tipo"] == "limite_contestado"


class TestLocalidades:
    def test_lee_con_poblacion_y_departamento(self, tmp_path):
        areas = leer("localidades", _localidades(tmp_path))
        salto = areas[0]
        assert (salto["nombre"], salto["departamento"], salto["codigo"]) == ("SALTO", "SALTO", 15020)
        assert salto["datos"] == {"poblacion_2023": 114043, "viviendas_2023": 41536, "capital": True}
        assert salto["tipo"] == "localidad"

    def test_un_punto_rural_da_la_mas_cercana_con_distancia(self, tmp_path):
        areas = leer("localidades", _localidades(tmp_path))
        assert ubicar(areas, -31.25, -57.55) is None
        area, km = mas_cercana(areas, -31.25, -57.55)
        assert area["nombre"] == "GARIBALDI"
        assert 4 < km < 8

    def test_las_capas_declaran_su_fuente(self):
        assert "INE" in CAPAS["departamentos"]["fuente"] and "INE" in CAPAS["localidades"]["fuente"]
