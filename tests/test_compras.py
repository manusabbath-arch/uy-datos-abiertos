"""Tests de `uydatos.compras`, sin red, con ZIP sintéticos que tienen la forma de los de la ARCE.

Cada clase fija una trampa medida el 10/10/2026 sobre los archivos de 2024 y 2025.
"""

from __future__ import annotations

import json
import zipfile
from datetime import date
from pathlib import Path

import pytest

from uydatos.compras import (
    BCU_POR_MONEDA,
    ComprasInvalido,
    convertir,
    leer_adjudicaciones,
    precios_de_referencia,
    resumen,
)


def _item(descripcion, cantidad, precio, moneda="UYU", catalogo="10233"):
    item = {
        "id": 1,
        "quantity": cantidad,
        "classification": {"id": catalogo, "description": descripcion, "scheme": "x_catalogo_arce"},
        "unit": {"id": "22", "name": "UNIDAD", "value": {"amount": precio}},
    }
    if moneda:
        item["unit"]["value"]["currency"] = moneda
    return item


def _adjudicacion(
    ocid, comprador, items, estado="active", fecha="2025-03-05T10:00:00Z", con_buyer=True, proveedor=True
):
    r = {
        "tag": ["award"],
        "ocid": f"ocds-yfs5dr-{ocid}",
        "id": f"adjudicacion-{ocid}",
        "date": fecha,
        "parties": [{"id": comprador[0], "roles": ["buyer", "procuringEntity"], "name": comprador[1]}],
        "awards": [{"id": "R/210000000019", "status": estado, "items": items}],
    }
    if con_buyer:
        r["buyer"] = {"id": comprador[0], "name": comprador[1]}
    if proveedor:
        r["awards"][0]["suppliers"] = [{"id": "R/210000000019", "name": "EMPRESA SA"}]
    return r


LLAMADO = {
    "tag": ["tender"],
    "ocid": "ocds-yfs5dr-i1",
    "id": "llamado-i1",
    "date": "2025-03-01T10:00:00Z",
    "tender": {"id": "i1", "title": "Licitación"},
    "awards": [{"id": "x", "value": {"amount": 999999, "currency": "UYU"}}],
}
ANULACION = {
    "tag": ["awardCancellation"],
    "ocid": "ocds-yfs5dr-868950",
    "id": "cancelacion_adjudicacion-868950",
    "date": "2025-03-02T10:00:00Z",
    "awards": [{"id": "868950", "status": "unsuccessful"}],
}
BSE = ("53-1", "Banco de Seguros del Estado")
IM = ("98-1", "Intendencia de Montevideo")


def _zip(tmp_path: Path, releases: list[dict], carpeta: str = "2025/", anio: int = 2025) -> Path:
    p = tmp_path / f"compras{anio}.zip"
    with zipfile.ZipFile(p, "w") as z:
        if carpeta:
            z.writestr(carpeta, "")
        z.writestr(f"{carpeta}a-03-{anio}.json", json.dumps({"version": "1.1", "releases": releases}))
        z.writestr(f"{carpeta}l-03-{anio}.json", json.dumps({"version": "1.1", "releases": [LLAMADO]}))
    return p


class TestEstructura:
    def test_2025_tiene_carpeta_y_2024_no(self, tmp_path):
        """En 2025 los JSON están en `2025/`; en 2024, sueltos. Buscar `/a-` en la ruta da 0 en 2024."""
        a = _adjudicacion(1, BSE, [_item("X", 1, 100)])
        assert len(leer_adjudicaciones(_zip(tmp_path, [a], "2025/"))) == 1
        assert len(leer_adjudicaciones(_zip(tmp_path, [a], "", 2024))) == 1

    def test_el_json_declarado_es_un_zip(self, tmp_path):
        """El catálogo lo declara JSON; un JSON de verdad se rechaza en vez de leerse como cero compras."""
        p = tmp_path / "compras2025.json"
        p.write_text('{"releases": []}', encoding="utf-8")
        with pytest.raises(ComprasInvalido, match="ZIP"):
            leer_adjudicaciones(p)

    def test_un_zip_sin_adjudicaciones_se_rechaza(self, tmp_path):
        p = tmp_path / "vacio.zip"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("otra-cosa.json", "{}")
        with pytest.raises(ComprasInvalido, match="a-MM"):
            leer_adjudicaciones(p)


class TestImporte:
    def test_el_total_es_cantidad_por_precio(self, tmp_path):
        """222.616 ítems de 2025 tienen cantidad distinta de 1: sumar el precio subestima."""
        (a,) = leer_adjudicaciones(
            _zip(tmp_path, [_adjudicacion(1, BSE, [_item("GUANTES", 200, 3.5), _item("TIMBRE", 1, 320000)])])
        )
        assert a["importes"] == {"UYU": 320700.0}
        assert [i["importe"] for i in a["items"]] == [700.0, 320000.0]

    def test_monedas_por_separado_y_sin_moneda_aparte(self, tmp_path):
        items = [_item("A", 2, 10, "USD"), _item("B", 1, 5, "UYI"), _item("C", 3, 1, None)]
        (a,) = leer_adjudicaciones(_zip(tmp_path, [_adjudicacion(1, BSE, items)]))
        assert a["importes"] == {"USD": 20.0, "UYI": 5.0}
        assert a["sin_moneda"] == 3.0


class TestQueEsUnaCompra:
    def test_llamados_y_anulaciones_no_son_compras(self, tmp_path):
        """El archivo de adjudicaciones trae llamados (con montos estimados) y anulaciones."""
        r = [_adjudicacion(1, BSE, [_item("X", 1, 100)]), LLAMADO, ANULACION]
        assert len(leer_adjudicaciones(_zip(tmp_path, r))) == 1

    def test_solo_las_activas_suman(self, tmp_path):
        r = [
            _adjudicacion(1, BSE, [_item("X", 1, 100)]),
            _adjudicacion(2, BSE, [_item("Y", 1, 50)], estado="cancelled"),
            _adjudicacion(3, BSE, [_item("Z", 1, 25)], estado="unsuccessful"),
        ]
        s = resumen(leer_adjudicaciones(_zip(tmp_path, r)))
        assert s["adjudicaciones"] == 1 and s["excluidas_por_estado"] == {"cancelled": 1, "unsuccessful": 1}
        assert s["importes"] == {"UYU": 100.0}

    def test_el_comprador_sale_de_parties_si_falta_buyer(self, tmp_path):
        (a,) = leer_adjudicaciones(_zip(tmp_path, [_adjudicacion(1, IM, [_item("X", 1, 1)], con_buyer=False)]))
        assert a["comprador"] == {"id": "98-1", "nombre": "Intendencia de Montevideo"}

    def test_una_adjudicacion_sin_comprador_se_lee_y_se_cuenta(self, tmp_path):
        """96 en 2024 y 53 en 2025 solo traen al proveedor: rechazar el año entero por eso sería peor."""
        sin = _adjudicacion(1, BSE, [_item("X", 1, 7)], con_buyer=False)
        sin["parties"] = [{"id": "R/210000000019", "roles": ["supplier"], "name": "EMPRESA SA"}]
        adjs = leer_adjudicaciones(_zip(tmp_path, [sin, _adjudicacion(2, IM, [_item("Y", 1, 3)])]))
        assert adjs[0]["comprador"] is None
        s = resumen(adjs)
        assert s["sin_comprador"] == 1 and s["importes"] == {"UYU": 10.0}
        assert resumen(adjs, organismo="intendencia de montevideo")["importes"] == {"UYU": 3.0}

    def test_una_adjudicacion_sin_proveedor_se_lee_y_se_cuenta(self, tmp_path):
        r = [_adjudicacion(1, BSE, [_item("X", 1, 1)], proveedor=False)]
        s = resumen(leer_adjudicaciones(_zip(tmp_path, r)))
        assert s["sin_proveedor"] == 1


class TestResumen:
    def test_filtra_por_organismo_y_por_texto_sin_tildes(self, tmp_path):
        r = [
            _adjudicacion(1, BSE, [_item("GUANTES DE LATEX", 10, 2)]),
            _adjudicacion(2, IM, [_item("SERVICIO DE LIMPIEZA", 1, 1000)]),
            _adjudicacion(3, IM, [_item("Guantes de nitrilo", 5, 4)]),
        ]
        adjs = leer_adjudicaciones(_zip(tmp_path, r))
        assert resumen(adjs, organismo="intendencia de montevideo")["importes"] == {"UYU": 1020.0}
        s = resumen(adjs, buscar="guantes")
        assert s["importes"] == {"UYU": 40.0} and s["items"] == 2

    def test_por_comprador_ordenado(self, tmp_path):
        r = [_adjudicacion(1, BSE, [_item("X", 1, 10)]), _adjudicacion(2, IM, [_item("Y", 1, 99)])]
        s = resumen(leer_adjudicaciones(_zip(tmp_path, r)))
        assert [c["nombre"] for c in s["por_comprador"]] == ["Intendencia de Montevideo", "Banco de Seguros del Estado"]


class TestConversion:
    def test_convierte_con_la_cotizacion_del_dia(self):
        cot = {(2225, date(2025, 3, 5)): 42.0, (9800, date(2025, 3, 5)): 6.2}
        r = convertir({"UYU": 100.0, "USD": 10.0, "UYI": 100.0}, date(2025, 3, 5), lambda c, d: cot.get((c, d)))
        assert r == {"pesos": 100.0 + 420.0 + 620.0, "sin_convertir": {}}

    def test_una_moneda_sin_cotizacion_queda_aparte(self):
        r = convertir({"UYU": 1.0, "XXX": 5.0, "EUR": 2.0}, date(2025, 3, 5), lambda c, d: None)
        assert r == {"pesos": 1.0, "sin_convertir": {"XXX": 5.0, "EUR": 2.0}}

    def test_las_monedas_que_aparecen_tienen_codigo_del_bcu(self):
        """Medido en 2025: UYU, USD, EUR, UYI, BRL, CHF y ZAR."""
        assert {"USD", "EUR", "UYI", "BRL", "CHF", "ZAR"} <= set(BCU_POR_MONEDA)


class TestConcentracion:
    """Un solo ítem de UTE es el 77% de lo adjudicado en pesos en 2024 (850.000 × 461.611) y otro el 53%
    en 2025 (798.848,2 × 88.760,8): el total anual está dominado por registros con cantidad × precio
    imposible. No se corrigen ni se descartan: se muestran, con su peso en el total y su ocid."""

    def test_los_mayores_items_con_su_peso_y_su_ocid(self, tmp_path):
        r = [
            _adjudicacion(1, BSE, [_item("ALAMBRADO", 850000, 461611)]),
            _adjudicacion(2, IM, [_item("LIMPIEZA", 1, 1000), _item("GUANTES", 10, 2)]),
        ]
        s = resumen(leer_adjudicaciones(_zip(tmp_path, r)))
        mayor = s["mayores_items"][0]
        assert (mayor["descripcion"], mayor["ocid"], mayor["comprador"]) == (
            "ALAMBRADO",
            "ocds-yfs5dr-1",
            "Banco de Seguros del Estado",
        )
        assert mayor["pct_del_total"] > 99.9
        assert s["concentracion_uyu"]["mayor_item_pct"] > 99.9
        assert len(s["mayores_items"]) == 3

    def test_sin_importes_en_pesos_no_hay_concentracion(self, tmp_path):
        s = resumen(leer_adjudicaciones(_zip(tmp_path, [_adjudicacion(1, BSE, [_item("X", 1, 5, "USD")])])))
        assert s["concentracion_uyu"] is None and s["mayores_items"] == []


class TestIterar:
    """`iterar_adjudicaciones` entrega una adjudicación por vez: quien compacta no necesita tener el
    año entero en memoria dos veces (medido el 2026-11-27: 343 MB el año 2025 leído con
    `leer_adjudicaciones`)."""

    def test_da_lo_mismo_que_leer(self, tmp_path):
        from uydatos.compras import iterar_adjudicaciones

        p = _zip(tmp_path, [_adjudicacion(1, BSE, [_item("X", 1, 100)]), _adjudicacion(2, IM, [_item("Y", 2, 3)])])
        it = iterar_adjudicaciones(p)
        assert not isinstance(it, list)
        assert list(it) == leer_adjudicaciones(p)

    def test_un_archivo_que_no_es_zip_se_rechaza_al_iterar(self, tmp_path):
        from uydatos.compras import iterar_adjudicaciones

        p = tmp_path / "compras2025.json"
        p.write_text('{"releases": []}', encoding="utf-8")
        with pytest.raises(ComprasInvalido, match="ZIP"):
            next(iterar_adjudicaciones(p))


def _llamado(ocid, modalidad, tag="tender", fecha="2025-03-01T10:00:00Z"):
    return {
        "tag": [tag],
        "ocid": f"ocds-yfs5dr-{ocid}",
        "id": f"llamado-{ocid}",
        "date": fecha,
        "tender": {"id": str(ocid), "procurementMethodDetails": modalidad, "title": f"{modalidad} 1/2025"},
    }


def _zip_con_llamados(tmp_path: Path, adjudicaciones: list[dict], llamados: list[dict]) -> Path:
    p = tmp_path / "compras2025.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("2025/a-03-2025.json", json.dumps({"version": "1.1", "releases": adjudicaciones}))
        z.writestr("2025/l-02-2025.json", json.dumps({"version": "1.1", "releases": llamados}))
    return p


class TestModalidad:
    """La modalidad (compra directa, licitación...) está en el llamado, no en la adjudicación. El 77 %
    de los procedimientos adjudicados en 2025 no tiene llamado en el archivo: su modalidad no se sabe."""

    def test_la_modalidad_sale_del_llamado_con_el_mismo_ocid(self, tmp_path):
        a = [_adjudicacion(1, IM, [_item("X", 1, 100)]), _adjudicacion(2, IM, [_item("Y", 1, 50)])]
        ll = [_llamado(1, "Compra Directa"), _llamado(2, "Licitación Abreviada")]
        r = leer_adjudicaciones(_zip_con_llamados(tmp_path, a, ll))
        assert [x["modalidad"] for x in r] == ["Compra Directa", "Licitación Abreviada"]

    def test_sin_llamado_la_modalidad_es_desconocida_no_compra_directa(self, tmp_path):
        """No se adivina: que falte el llamado no prueba que sea compra directa."""
        (x,) = leer_adjudicaciones(_zip_con_llamados(tmp_path, [_adjudicacion(7, IM, [_item("X", 1, 1)])], []))
        assert x["modalidad"] is None

    def test_vale_la_ultima_actualizacion_del_llamado(self, tmp_path):
        ll = [
            _llamado(1, "Compra Directa", "tenderUpdate", "2025-03-03T10:00:00Z"),
            _llamado(1, "Licitación Abreviada", "tender", "2025-03-01T10:00:00Z"),
        ]
        (x,) = leer_adjudicaciones(_zip_con_llamados(tmp_path, [_adjudicacion(1, IM, [_item("X", 1, 1)])], ll))
        assert x["modalidad"] == "Compra Directa"

    def test_un_llamado_dentro_del_archivo_de_adjudicaciones_tambien_cuenta(self, tmp_path):
        r = [_llamado(5, "Compra por Excepción"), _adjudicacion(5, IM, [_item("X", 1, 1)])]
        (x,) = leer_adjudicaciones(_zip_con_llamados(tmp_path, r, []))
        assert x["modalidad"] == "Compra por Excepción"

    def test_el_resumen_cuenta_por_modalidad_y_las_desconocidas_aparte(self, tmp_path):
        a = [_adjudicacion(i, IM, [_item("X", 1, 10)]) for i in (1, 2, 3, 4)]
        ll = [_llamado(1, "Compra Directa"), _llamado(2, "Compra Directa"), _llamado(3, "Compra por Excepción")]
        s = resumen(leer_adjudicaciones(_zip_con_llamados(tmp_path, a, ll)))
        assert s["por_modalidad"] == {"Compra Directa": 2, "Compra por Excepción": 1}
        assert s["sin_modalidad"] == 1

    def test_el_resumen_filtra_por_modalidad_sin_tildes(self, tmp_path):
        a = [_adjudicacion(i, IM, [_item("X", 1, 10 * i)]) for i in (1, 2, 3)]
        ll = [_llamado(1, "Compra por Excepción"), _llamado(2, "Licitación Pública")]
        s = resumen(leer_adjudicaciones(_zip_con_llamados(tmp_path, a, ll)), modalidad="compra por excepcion")
        assert s["adjudicaciones"] == 1 and s["importes"] == {"UYU": 10.0}
        assert s["sin_modalidad"] == 1  # la del ocid 3 no se sabe: se avisa, no se descarta en silencio


def _item_u(descripcion, precio, unidad="UNIDAD", catalogo="37021", moneda="UYU", cantidad=1):
    it = _item(descripcion, cantidad, precio, moneda, catalogo)
    it["unit"]["name"] = unidad
    return it


class TestPreciosDeReferencia:
    """Lo que pidieron los compradores en la consulta de ARCE (2023): precios de procesos anteriores.
    Medido sobre 2025: «guantes de látex descartable no estéril» (catálogo 37021) se compra por UNIDAD
    (mediana $1,13) y por CAJA (mediana $113), con una «caja» a $0,14. No se mezclan unidades."""

    def test_el_item_trae_la_unidad(self, tmp_path):
        (a,) = leer_adjudicaciones(_zip(tmp_path, [_adjudicacion(1, IM, [_item_u("GUANTES", 1.1, "CAJA")])]))
        assert a["items"][0]["unidad"] == "CAJA"

    def test_agrupa_por_catalogo_unidad_y_moneda_sin_mezclar(self, tmp_path):
        r = [
            _adjudicacion(1, IM, [_item_u("GUANTES DE LATEX", 1.0)]),
            _adjudicacion(2, BSE, [_item_u("GUANTES DE LATEX", 1.2)]),
            _adjudicacion(3, IM, [_item_u("GUANTES DE LATEX", 1.4)]),
            _adjudicacion(4, IM, [_item_u("GUANTES DE LATEX", 113.0, "CAJA")]),
            _adjudicacion(5, IM, [_item_u("GUANTES DE LATEX", 2.0, moneda="USD")]),
        ]
        g = precios_de_referencia(leer_adjudicaciones(_zip(tmp_path, r)), buscar="guantes de látex")
        claves = [(x["catalogo"], x["unidad"], x["moneda"], x["n"]) for x in g["grupos"]]
        assert claves[0] == ("37021", "UNIDAD", "UYU", 3)
        assert set(claves[1:]) == {("37021", "CAJA", "UYU", 1), ("37021", "UNIDAD", "USD", 1)}
        primero = g["grupos"][0]
        assert (primero["minimo"], primero["mediana"], primero["maximo"]) == (1.0, 1.2, 1.4)
        assert primero["organismos"] == 2

    def test_precio_cero_sin_moneda_y_sin_unidad_se_excluyen_con_motivo(self, tmp_path):
        r = [
            _adjudicacion(1, IM, [_item_u("HIPOCLORITO", 0.0, "L")]),
            _adjudicacion(2, IM, [_item_u("HIPOCLORITO", 20.0, "L", moneda=None)]),
            _adjudicacion(3, IM, [_item_u("HIPOCLORITO", 20.0, "-----")]),
            _adjudicacion(4, IM, [_item_u("HIPOCLORITO", 20.0, "L")]),
        ]
        g = precios_de_referencia(leer_adjudicaciones(_zip(tmp_path, r)), buscar="hipoclorito")
        assert g["excluidos"] == {"precio_cero": 1, "sin_moneda": 1, "sin_unidad": 1}
        assert [x["n"] for x in g["grupos"]] == [1]

    def test_los_atipicos_se_senalan_con_su_ocid_y_no_se_descartan(self, tmp_path):
        """Una «caja» a $0,14 entre cajas de $100: se señala (diez veces de la mediana), no se borra."""
        precios = [100, 105, 110, 115, 120, 0.14]
        r = [_adjudicacion(i, IM, [_item_u("GUANTES", p, "CAJA")]) for i, p in enumerate(precios, 1)]
        (grupo,) = precios_de_referencia(leer_adjudicaciones(_zip(tmp_path, r)), buscar="guantes")["grupos"]
        assert grupo["n"] == 6
        assert [(x["ocid"], x["precio_unitario"]) for x in grupo["atipicos"]] == [("ocds-yfs5dr-6", 0.14)]

    def test_con_menos_de_cinco_precios_no_se_senalan_atipicos(self, tmp_path):
        r = [_adjudicacion(i, IM, [_item_u("GUANTES", p, "CAJA")]) for i, p in enumerate([100, 0.14], 1)]
        (grupo,) = precios_de_referencia(leer_adjudicaciones(_zip(tmp_path, r)), buscar="guantes")["grupos"]
        assert grupo["atipicos"] == []

    def test_solo_adjudicaciones_activas_y_filtra_por_organismo(self, tmp_path):
        r = [
            _adjudicacion(1, IM, [_item_u("GUANTES", 1.0)]),
            _adjudicacion(2, IM, [_item_u("GUANTES", 9.0)], estado="cancelled"),
            _adjudicacion(3, BSE, [_item_u("GUANTES", 5.0)]),
        ]
        g = precios_de_referencia(leer_adjudicaciones(_zip(tmp_path, r)), buscar="guantes", organismo="98-1")
        assert [x["mediana"] for x in g["grupos"]] == [1.0]

    def test_sin_buscar_se_rechaza(self, tmp_path):
        """Un precio de referencia de «todo» no existe: sin producto no hay comparación."""
        with pytest.raises(ValueError, match="buscar"):
            precios_de_referencia([], buscar=" ")


class TestModalidadPorOrganismo:
    def test_cada_comprador_dice_cuantas_no_traen_modalidad(self, tmp_path):
        a = [_adjudicacion(1, IM, [_item("X", 1, 1)]), _adjudicacion(2, IM, [_item("X", 1, 1)]),
             _adjudicacion(3, BSE, [_item("X", 1, 1)])]  # fmt: skip
        s = resumen(leer_adjudicaciones(_zip_con_llamados(tmp_path, a, [_llamado(1, "Compra Directa")])))
        por = {c["nombre"]: c["sin_modalidad"] for c in s["por_comprador"]}
        assert por == {IM[1]: 1, BSE[1]: 1}
