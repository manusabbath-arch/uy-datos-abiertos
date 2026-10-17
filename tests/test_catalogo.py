"""Tests de `uydatos.catalogo`: la respuesta de `package_show` de CKAN, sin red."""

from __future__ import annotations

import pytest

from uydatos import catalogo
from uydatos.catalogo import CatalogoInvalido, parsear_package_show


def _respuesta(recursos, success=True):
    return {"success": success, "result": {"resources": recursos}}


def test_lista_los_recursos():
    r = parsear_package_show(
        _respuesta(
            [
                {
                    "name": "ppt_tmax_tmin_sg_2026",
                    "url": "https://catalogodatos.gub.uy/x/ppt_tmax_tmin_sg_2026.csv",
                    "format": "csv",
                    "last_modified": "2026-09-11T10:00:00",
                }
            ]
        )
    )
    assert r == [
        {
            "nombre": "ppt_tmax_tmin_sg_2026",
            "url": "https://catalogodatos.gub.uy/x/ppt_tmax_tmin_sg_2026.csv",
            "formato": "CSV",
            "modificado": "2026-09-11T10:00:00",
        }
    ]


def test_success_falso_se_rechaza():
    with pytest.raises(CatalogoInvalido, match="success"):
        parsear_package_show({"success": False, "error": {"message": "Not found"}})


def test_dataset_sin_recursos_se_rechaza():
    with pytest.raises(CatalogoInvalido, match="recursos"):
        parsear_package_show(_respuesta([]))


CRUDO_BUSQUEDA = {
    "count": 1875,
    "facets": {"organization": {"mides": 1875}, "res_format": {"CSV": 1800}},
    "results": [
        {
            "name": "mides-indicador-10745",
            "title": "Demanda bioquimica de oxigeno industrial",
            "organization": {"name": "mides"},
            "metadata_modified": "2026-10-01T12:00:00.123456",
            "resources": [{"format": "CSV"}, {"format": "json"}, {"format": "CSV"}],
        }
    ],
}


class TestBuscar:
    def test_parsear_busqueda_no_arrastra_la_grasa(self):
        r = catalogo.parsear_busqueda(CRUDO_BUSQUEDA)
        assert r["total"] == 1875
        assert r["organizaciones"] == {"mides": 1875}
        assert r["formatos"]["CSV"] == 1800
        (d,) = r["datasets"]
        assert d["nombre"] == "mides-indicador-10745"
        assert d["organizacion"] == "mides"
        assert d["formatos"] == ["CSV", "JSON"]

    def test_buscar_arma_fq_sin_tocar_el_texto_libre(self, monkeypatch):
        visto = {}

        def falso(nombre, **p):
            visto.update(nombre=nombre, **p)
            return {"count": 0, "facets": {}, "results": []}

        monkeypatch.setattr(catalogo, "accion", falso)
        catalogo.buscar("clima", organizacion="inumet", formato="csv")
        assert visto["nombre"] == "package_search"
        assert visto["q"] == "clima"
        assert visto["fq"] == "organization:inumet res_format:CSV"
        assert visto["rows"] == 10
        assert "facet.field" in visto

    def test_la_cantidad_de_filas_se_limita(self, monkeypatch):
        visto = {}

        def falso(nombre, **p):
            visto.update(p)
            return {"count": 0, "facets": {}, "results": []}

        monkeypatch.setattr(catalogo, "accion", falso)
        catalogo.buscar(filas=0)
        assert visto["rows"] == 1
        catalogo.buscar(filas=500)
        assert visto["rows"] == 100

    def test_sin_filtros_no_se_manda_fq(self, monkeypatch):
        visto = {}

        def falso(nombre, **p):
            visto.update(p)
            return {"count": 0, "facets": {}, "results": []}

        monkeypatch.setattr(catalogo, "accion", falso)
        catalogo.buscar("agua")
        assert "fq" not in visto


class TestAccion:
    def test_una_accion_con_success_falso_levanta_con_el_motivo(self, monkeypatch):
        monkeypatch.setattr(
            "uydatos.red.pedir",
            lambda url, **p: b'{"success": false, "error": {"message": "Not found"}}',
        )
        with pytest.raises(catalogo.CatalogoInvalido, match="Not found"):
            catalogo.accion("package_show", id="no-existe")

    def test_una_accion_buena_devuelve_solo_el_result(self, monkeypatch):
        monkeypatch.setattr("uydatos.red.pedir", lambda url, **p: b'{"success": true, "result": {"count": 3}}')
        assert catalogo.accion("package_search", q="") == {"count": 3}


class TestDatastore:
    def test_parsear_datastore_declara_que_todo_es_texto(self, monkeypatch):
        crudo = {
            "total": 332071,
            "fields": [{"id": "_id", "type": "int"}, {"id": "fecha", "type": "text"}],
            "records": [{"_id": 1, "fecha": "2026-10-09 00:00"}],
        }
        monkeypatch.setattr(catalogo, "accion", lambda nombre, **p: crudo)
        r = catalogo.datastore_search("f800fc53-556b-4d1c-8bd6-28b41f9cf146")
        assert r["total"] == 332071
        assert r["campos"] == ["_id", "fecha"]
        assert r["filas"] == [{"_id": 1, "fecha": "2026-10-09 00:00"}]


class TestFormatoSinImportarMayusculas:
    """El filtro `res_format` de CKAN distingue mayúsculas, y el catálogo mezcla: medido el 10/10/2026,
    21 recursos «GeoJSON» y ninguno «GEOJSON», y «csv zip» junto a «CSV ZIP». Pasar el formato a
    mayúsculas devolvía 0 para geojson: un cero que parece un dato."""

    def _falso(self, facetas, visto):
        def accion(nombre, **p):
            if p.get("rows") == 0:
                return {"count": 0, "facets": {"res_format": facetas}, "results": []}
            visto.update(p)
            return {"count": 0, "facets": {}, "results": []}

        return accion

    def test_geojson_encuentra_la_variante_que_existe(self, monkeypatch):
        visto = {}
        monkeypatch.setattr(catalogo, "accion", self._falso({"GeoJSON": 21, "CSV": 10}, visto))
        catalogo.buscar("", formato="geojson")
        assert visto["fq"] == "res_format:GeoJSON"

    def test_varias_variantes_van_juntas(self, monkeypatch):
        visto = {}
        monkeypatch.setattr(catalogo, "accion", self._falso({"csv zip": 8, "CSV ZIP": 7, "CSV": 9}, visto))
        catalogo.buscar("", formato="CSV ZIP")
        assert visto["fq"] == 'res_format:("CSV ZIP" OR "csv zip")'


class TestMapaDelCatalogo:
    """El mapa del catálogo: los dos endpoints no cuentan lo mismo (medido el 2026-10-17: 2.777 por
    `package_list` y 2.716 por `package_search`), y el histograma de formatos sale completo del
    facet, sin paginar."""

    def test_formatos_usa_el_facet_completo(self, monkeypatch):
        visto = {}

        def falso(nombre, **p):
            visto.update(nombre=nombre, **p)
            return {"count": 2777, "facets": {"res_format": {"CSV": 1100, "PDF": 800}}, "results": []}

        monkeypatch.setattr(catalogo, "accion", falso)
        assert catalogo.formatos() == {"CSV": 1100, "PDF": 800}
        assert visto["nombre"] == "package_search"
        assert visto["rows"] == 0
        assert visto["q"] == "*:*"
        assert "res_format" in visto["facet.field"]

    def test_todos_pagina_hasta_el_conteo(self, monkeypatch):
        llamadas = []

        def falso(nombre, **p):
            llamadas.append(p["start"])
            if p["start"] == 0:
                return {"count": 1700, "results": [{"name": f"d{i}"} for i in range(1000)]}
            return {"count": 1700, "results": [{"name": f"d{i}"} for i in range(1000, 1700)]}

        monkeypatch.setattr(catalogo, "accion", falso)
        nombres = catalogo.todos()
        assert len(nombres) == 1700
        assert llamadas == [0, 1000]

    def test_faltantes_es_la_diferencia_entre_los_dos_endpoints(self, monkeypatch):
        monkeypatch.setattr(catalogo, "nombres", lambda: ["a", "b", "c", "d", "e"])
        monkeypatch.setattr(catalogo, "todos", lambda: ["a", "b", "c"])
        assert catalogo.faltantes() == {"en_lista": 5, "en_busqueda": 3, "faltan": ["d", "e"]}

    def test_el_buscador_no_puede_ver_mas_datasets_que_la_lista(self, monkeypatch):
        monkeypatch.setattr(catalogo, "nombres", lambda: ["a"])
        monkeypatch.setattr(catalogo, "todos", lambda: ["a", "z"])
        with pytest.raises(CatalogoInvalido, match="no están en package_list"):
            catalogo.faltantes()


@pytest.mark.red
def test_los_dos_endpoints_del_catalogo_real():
    """El mismo catálogo por `package_list` y por `package_search`. Medido el 2026-10-17: 2.777 y
    2.716, y los 61 que faltan son fichas `state=active` con cero recursos (visualizadores, apps).
    Se afirma una relación (la búsqueda no ve más que la lista) y un orden de magnitud, no un número
    exacto: el total puede bajar."""
    en_lista = catalogo.nombres()
    en_busqueda = catalogo.todos()
    assert 2000 <= len(en_lista), f"package_list trajo {len(en_lista)} datasets"
    assert set(en_busqueda) <= set(en_lista), "la búsqueda ve datasets que la lista no tiene"
    print(
        f"\npackage_list {len(en_lista)} · package_search {len(en_busqueda)}"
        f" · faltan {len(set(en_lista) - set(en_busqueda))}"
    )
