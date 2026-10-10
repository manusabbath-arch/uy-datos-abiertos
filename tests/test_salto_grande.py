"""Tests del lector del webservice de Salto Grande (CTM).

Fijan lo que puede romperse en silencio y producir una lista creible pero falsa:

- **`TestSoapEncoded`**: la respuesta es SOAP **encoded** (`SOAP-ENC:arrayType`) y los
  elementos del arreglo se llaman **`item`**, no `Estacion`. Un lector que busque por nombre
  de elemento (`findall('Estacion')`) no encuentra nada y devuelve una lista **vacia** sin
  error: `0 estaciones` parece un servicio caido, no un lector roto.
- **`TestNillable`**: `Latitud`/`Longitud` son `nillable="true"`. Una estacion sin coordenada
  viene con `xsi:nil="true"`; el lector la deja en `None` y **no** revienta en `float("")`.
- **`TestUnidades`**: el WSDL **no declara unidades**. El lector devuelve los valores crudos
  (P, H, Q) y **no** los etiqueta como mm/m³·s por su cuenta: seria inventar una unidad.
- **`TestRecorteReal`**: los tests leen un recorte de la respuesta real, no la red. `descargar_lista()` es
  la unica funcion que sale a internet.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from uydatos.salto_grande import (
    SaltoGrandeInvalido,
    distancia_km,
    estaciones_cerca_de,
    leer_estaciones,
)

SOAP_VACIO = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"'
    ' xmlns:ns1="https://www.saltogrande.org/ws.php"'
    ' xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/"'
    ' xmlns:xsd="http://www.w3.org/2001/XMLSchema"'
    ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
    '<SOAP-ENV:Body><ns1:X><return SOAP-ENC:arrayType="ns1:Estacion[0]">'
    "</return></ns1:X></SOAP-ENV:Body></SOAP-ENV:Envelope>"
)


def _soap(estaciones: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"'
        ' xmlns:ns1="https://www.saltogrande.org/ws.php"'
        ' xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/"'
        ' xmlns:xsd="http://www.w3.org/2001/XMLSchema"'
        ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        "<SOAP-ENV:Body><ns1:X><return>" + estaciones + "</return></ns1:X>"
        "</SOAP-ENV:Body></SOAP-ENV:Envelope>"
    )


ITEM = (
    '<item xsi:type="ns1:Estacion">'
    '<Id xsi:type="xsd:string">A501258E</Id>'
    '<Nombre xsi:type="xsd:string">Salto</Nombre>'
    '<Latitud xsi:type="xsd:float">-31.38978</Latitud>'
    '<Longitud xsi:type="xsd:float">-57.977472</Longitud>'
    '<Fecha xsi:type="xsd:string">2026-10-04 17:45:00</Fecha>'
    '<Variables SOAP-ENC:arrayType="xsd:string[1]" xsi:type="SOAP-ENC:Array">'
    '<item xsi:type="xsd:string">P</item></Variables></item>'
)

ITEM_NIL = (
    '<item xsi:type="ns1:Estacion">'
    '<Id xsi:type="xsd:string">A5000000</Id>'
    '<Nombre xsi:type="xsd:string">Sin Coordenada</Nombre>'
    '<Latitud xsi:type="xsd:float" xsi:nil="true"/>'
    '<Longitud xsi:type="xsd:float" xsi:nil="true"/>'
    '<Fecha xsi:type="xsd:string">2026-10-04 18:00:00</Fecha>'
    "</item>"
)


class TestSoapEncoded:
    def test_lee_un_item(self, tmp_path):
        f = tmp_path / "r.xml"
        f.write_text(_soap(ITEM), encoding="utf-8")
        ests = leer_estaciones(f)
        assert len(ests) == 1
        assert ests[0]["id"] == "A501258E"
        assert ests[0]["nombre"] == "Salto"
        assert ests[0]["lat"] == pytest.approx(-31.38978)

    def test_el_arreglo_son_items_no_estacion(self, tmp_path):
        """El tag del elemento es `item`: buscar por `Estacion` da lista vacia."""
        f = tmp_path / "r.xml"
        f.write_text(_soap(ITEM + ITEM_NIL), encoding="utf-8")
        assert len(leer_estaciones(f)) == 2

    def test_un_arreglo_vacio_se_rechaza(self, tmp_path):
        """0 estaciones no es una lista valida: es un lector roto o el servicio caido."""
        f = tmp_path / "r.xml"
        f.write_text(SOAP_VACIO, encoding="utf-8")
        with pytest.raises(SaltoGrandeInvalido, match="sin estaciones"):
            leer_estaciones(f)

    def test_un_xml_que_no_es_soap_se_rechaza(self, tmp_path):
        f = tmp_path / "r.xml"
        f.write_text("<html><body>404</body></html>", encoding="utf-8")
        with pytest.raises(SaltoGrandeInvalido, match="return|soap|SOAP"):
            leer_estaciones(f)


class TestNillable:
    def test_una_estacion_sin_coordenada_no_revienta(self, tmp_path):
        f = tmp_path / "r.xml"
        f.write_text(_soap(ITEM_NIL), encoding="utf-8")
        e = leer_estaciones(f)[0]
        assert e["lat"] is None and e["lon"] is None

    def test_las_variables_son_una_lista(self, tmp_path):
        f = tmp_path / "r.xml"
        f.write_text(_soap(ITEM), encoding="utf-8")
        assert leer_estaciones(f)[0]["variables"] == ["P"]


class TestUnidades:
    def test_no_inventa_unidades(self, tmp_path):
        """El WSDL no declara unidades: el lector no las etiqueta."""
        f = tmp_path / "r.xml"
        f.write_text(_soap(ITEM), encoding="utf-8")
        e = leer_estaciones(f)[0]
        assert "unidad" not in e
        assert "unidades" not in e


class TestGeo:
    def test_distancia_de_salto_a_si_misma_es_cero(self):
        assert distancia_km(-31.383, -57.960, -31.383, -57.960) == pytest.approx(0.0, abs=0.01)

    def test_las_cerca_de_salto_estan_ordenadas(self):
        ests = [
            {"id": "lejos", "nombre": "Federación", "lat": -30.99, "lon": -57.91, "variables": []},
            {"id": "cerca", "nombre": "Salto", "lat": -31.38978, "lon": -57.977472, "variables": []},
        ]
        cerca = estaciones_cerca_de(ests, -31.383, -57.960)
        assert cerca[0][0]["id"] == "cerca"
        assert cerca[0][1] < cerca[1][1]

    def test_una_estacion_sin_coordenada_no_entra_al_ranking(self):
        ests = [{"id": "x", "nombre": "X", "lat": None, "lon": None, "variables": []}]
        assert estaciones_cerca_de(ests, -31.383, -57.960) == []


class TestRecorteReal:
    """Tres estaciones recortadas de la respuesta real del 04/10/2026."""

    RUTA = Path(__file__).parent / "fixtures" / "salto_grande_estaciones_recorte.xml"

    def test_la_respuesta_real_se_lee(self):
        nombres = {e["nombre"] for e in leer_estaciones(self.RUTA)}
        assert {"Salto", "Puerto Concordia"} <= nombres

    def test_hay_una_estacion_a_menos_de_5_km_del_centro_de_salto(self):
        cerca = estaciones_cerca_de(leer_estaciones(self.RUTA), -31.383, -57.960)
        assert cerca[0][0]["nombre"] == "Salto"
        assert cerca[0][1] < 5.0


class TestPedido:
    def test_user_agent_propio(self):
        """El servidor responde 403 a `Python-urllib/*` (medido el 09/10/2026)."""
        from uydatos.salto_grande import _pedido

        ua = _pedido().get_header("User-agent") or ""
        assert ua and not ua.lower().startswith("python-urllib")


# --- Lecturas (DatosHidrometeorologicos) ----------------------------------------------------------

from datetime import date, datetime  # noqa: E402

from uydatos.salto_grande import (  # noqa: E402
    SIN_DATO,
    cobertura,
    leer_datos,
    resumen_diario,
    tramos,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _datos(filas: str) -> str:
    return _soap(filas).replace("<return>", '<return SOAP-ENC:arrayType="ns1:DatoHidrometeorologico[1]">')


def _item(fecha, p="0", h="11.43", q="-999"):
    return (
        '<item xsi:type="ns1:DatoHidrometeorologico">'
        f'<Fecha xsi:type="xsd:string">{fecha}</Fecha><P xsi:type="xsd:float">{p}</P>'
        f'<H xsi:type="xsd:float">{h}</H><Q xsi:type="xsd:float">{q}</Q></item>'
    )


class TestLecturas:
    def test_el_recorte_real_se_lee(self):
        filas = leer_datos(FIXTURES / "salto_grande_datos_recorte.xml")
        assert filas[0] == {"fecha": datetime(2026, 10, 8, 0, 0), "P": 0.0, "H": 11.43, "Q": None}
        assert filas[-1]["fecha"] == datetime(2026, 10, 9, 0, 0)

    def test_menos_999_es_sin_dato_no_un_numero(self):
        """Medido el 10/10/2026: la estación Salto publica Q = -999 en todas las lecturas."""
        assert SIN_DATO == -999.0
        f = leer_datos(FIXTURES / "salto_grande_datos_recorte.xml")
        assert all(x["Q"] is None for x in f)

    def test_un_error_del_servidor_se_rechaza_con_su_mensaje(self):
        """Más de 31 días no da lista vacía: da un SOAP Fault, y el lector lo dice."""
        with pytest.raises(SaltoGrandeInvalido, match="31"):
            leer_datos(FIXTURES / "salto_grande_fault_31_dias.xml")

    def test_una_lista_vacia_es_valida(self, tmp_path):
        """Un rango sin lecturas es posible (hay huecos); quien llama mide la cobertura."""
        f = tmp_path / "r.xml"
        f.write_text(_datos(""), encoding="utf-8")
        assert leer_datos(f) == []

    def test_fecha_repetida_se_rechaza(self, tmp_path):
        f = tmp_path / "r.xml"
        f.write_text(_datos(_item("2026-10-08 00:00:00") + _item("2026-10-08 00:00:00")), encoding="utf-8")
        with pytest.raises(SaltoGrandeInvalido, match="repetid"):
            leer_datos(f)


class TestTramos:
    def test_un_mes_entra_en_un_tramo(self):
        assert tramos(date(2026, 10, 1), date(2026, 10, 31)) == [(date(2026, 10, 1), date(2026, 11, 1))]

    def test_el_hasta_incluye_el_dia_entero(self):
        """El servicio toma `fechaHasta` como las 00:00: para incluir el día se pide hasta el siguiente."""
        assert tramos(date(2026, 10, 8), date(2026, 10, 8)) == [(date(2026, 10, 8), date(2026, 10, 9))]

    def test_un_rango_largo_se_parte_en_tramos_de_hasta_31_dias(self):
        t = tramos(date(2026, 1, 1), date(2026, 3, 31))
        assert t[0][0] == date(2026, 1, 1) and t[-1][1] == date(2026, 4, 1)
        assert all((b - a).days <= 31 for a, b in t)
        assert all(t[i][1] == t[i + 1][0] for i in range(len(t) - 1))

    def test_desde_posterior_a_hasta(self):
        with pytest.raises(ValueError):
            tramos(date(2026, 2, 1), date(2026, 1, 1))


class TestResumen:
    def _lecturas(self):
        return [
            {"fecha": datetime(2026, 10, 8, 0, 0), "P": 0.0, "H": 11.0, "Q": None},
            {"fecha": datetime(2026, 10, 8, 12, 0), "P": 2.0, "H": 12.0, "Q": None},
            {"fecha": datetime(2026, 10, 9, 0, 0), "P": 0.0, "H": None, "Q": None},
        ]

    def test_por_dia_con_cuantas_lecturas(self):
        r = resumen_diario(self._lecturas(), "H")
        assert r == [
            {"dia": date(2026, 10, 8), "min": 11.0, "media": 11.5, "max": 12.0, "lecturas": 2},
            {"dia": date(2026, 10, 9), "min": None, "media": None, "max": None, "lecturas": 0},
        ]

    def test_cobertura_contra_96_lecturas_por_dia(self):
        c = cobertura(self._lecturas(), date(2026, 10, 8), date(2026, 10, 9))
        assert c == {"esperadas": 192, "recibidas": 3, "con_H": 2}
