"""Tests de `uydatos.ideuy`, sin red. Las respuestas tienen la forma real de la API, con
direcciones y coordenadas sintéticas.

Lo que se prueba de verdad:
  1. Que el centroide de la localidad no pasa por la coordenada de la dirección.
  2. Que una puerta ajustada por la API no se reporta como exacta.
  3. Que una respuesta de OTRA calle se descarta (`calle_distinta`): pedir una calle inexistente
     devolvió "CALLE N 2570" con aviso 'APROXIMADO POR CALLE' (medido el 09/10/2026).
  4. Que de v1 solo se acepta una ESQUINA, y que una esquina le gana al centro de una avenida.
"""

from __future__ import annotations

from uydatos.ideuy import (
    CALLE,
    CALLE_DISTINTA,
    ESQUINA,
    LOCALIDAD,
    NO_ENCONTRADO,
    PUERTA_APROXIMADA,
    PUERTA_EXACTA,
    clasificar_v0,
    clasificar_v1,
    coordenadas_v0,
    coordenadas_v1,
    dentro_de_uruguay,
    distancia_km,
    elegir_v0,
    es_esquina,
    extraer_numero_puerta,
    interpretar,
    misma_calle,
    url_v0,
    url_v1,
)


def _v0(calle=None, puerta=None, localidad="SALTO", tipo=1, error="", x=-57.96, y=-31.39):
    d = {"localidad": {"nombre_normalizado": localidad}}
    if calle:
        d["calle"] = {"nombre_normalizado": calle}
    if puerta is not None:
        d["numero"] = {"nro_puerta": puerta}
    return {"idTipoClasificacion": tipo, "error": error, "puntoX": x, "puntoY": y, "direccion": d}


EXACTA = _v0("JOSE PEDRO VARELA", 1500)
AJUSTADA = _v0("ARTIGAS", 1207, error="PUNTO NO ENCONTRADO.\nAPROXIMADO POR CALLE: \n")
CENTROIDE = _v0(tipo=3, error="PUNTO NO ENCONTRADO.\nAPROXIMADO POR LOCALIDAD A: \nSALTO")
CALLE_SOLA = _v0("URUGUAY", tipo=27)
OTRA_CALLE = _v0("CALLE N", 2570, error="PUNTO NO ENCONTRADO.\nAPROXIMADO POR CALLE: ")

V1_ESQUINA = {"type": "ESQUINA", "state": 1, "lat": -34.90, "lng": -56.18, "address": "AV 18 DE JULIO ESQ EJIDO"}
V1_OTRA = {"type": "CALLE", "state": 1, "lat": -31.40, "lng": -57.98, "address": "OTRA CALLE, SALTO, SALTO"}


class TestCoordenadas:
    def test_v0_puntox_es_la_longitud(self):
        """Trasponerlas no da error: en Uruguay las dos son negativas y plausibles."""
        assert coordenadas_v0(EXACTA) == (-31.39, -57.96)
        assert coordenadas_v0({}) is None

    def test_v1(self):
        assert coordenadas_v1(V1_ESQUINA) == (-34.90, -56.18)


class TestNumeroDePuerta:
    def test_calle_y_numero(self):
        assert extraer_numero_puerta("J. P. VARELA 1500") == 1500

    def test_fecha_en_el_nombre_de_la_calle(self):
        assert extraer_numero_puerta("18 DE JULIO 1234") == 1234
        assert extraer_numero_puerta("25 DE AGOSTO") is None

    def test_parentesis_local_y_ruta(self):
        assert extraer_numero_puerta("URUGUAY 999 (BARRIO CENTRO)") == 999
        assert extraer_numero_puerta("LOCAL Nº 5 Bº NORTE") is None
        assert extraer_numero_puerta("RUTA 3 KM 405") is None


class TestEsquina:
    def test_formatos(self):
        assert es_esquina("ARTIGAS 691 esq. Av. Solari")
        assert es_esquina("18 DE JULIO Y EJIDO")
        assert not es_esquina("JOSE P. VARELA 1500")


class TestMismaCalle:
    def test_abreviaturas_y_titulos(self):
        assert misma_calle("J. P. VARELA 1500", "JOSE PEDRO VARELA")
        assert misma_calle("Av. 18 de Julio 1360", "AVENIDA 18 DE JULIO")
        assert misma_calle("Dr. Luis Morquio 12", "DOCTOR LUIS MORQUIO")

    def test_tildes(self):
        assert misma_calle("Constitución 100", "CONSTITUCION")

    def test_otra_calle(self):
        assert not misma_calle("Calle que no existe 123", "CALLE N")

    def test_esquina_compara_la_primera_calle(self):
        assert misma_calle("Artigas 691 esq. Solari", "ARTIGAS")

    def test_sin_palabras_para_comparar_no_se_descarta(self):
        """'Calle 5 1200' no deja ninguna palabra útil: no hay cómo verificar, no se inventa un rechazo."""
        assert misma_calle("Calle 5 1200", "CALLE 5")


class TestClasificarV0:
    def test_puerta_exacta(self):
        assert clasificar_v0(EXACTA, 1500, "JOSE PEDRO VARELA 1500") == PUERTA_EXACTA

    def test_puerta_ajustada_es_aproximada(self):
        assert clasificar_v0(AJUSTADA, 1210, "ARTIGAS 1210") == PUERTA_APROXIMADA

    def test_puerta_devuelta_sin_numero_pedido(self):
        assert clasificar_v0(EXACTA, None) == PUERTA_APROXIMADA

    def test_centroide_de_localidad(self):
        assert clasificar_v0(CENTROIDE, None) == LOCALIDAD
        assert clasificar_v0({}, None) == LOCALIDAD

    def test_calle_sin_numero(self):
        assert clasificar_v0(CALLE_SOLA, None, "URUGUAY") == CALLE

    def test_otra_calle_se_descarta(self):
        """Medido el 09/10/2026: una calle inexistente devolvió 'CALLE N 2570'."""
        assert clasificar_v0(OTRA_CALLE, 123, "CALLE QUE NO EXISTE 123") == CALLE_DISTINTA


class TestElegirV0:
    def test_prefiere_la_puerta_sobre_el_centroide(self):
        assert elegir_v0([CENTROIDE, EXACTA], 1500, "J P VARELA 1500") == (PUERTA_EXACTA, EXACTA)

    def test_sin_resultados(self):
        assert elegir_v0([], 1500) == (NO_ENCONTRADO, None)

    def test_solo_descartables_no_devuelven_item(self):
        assert elegir_v0([CENTROIDE], None) == (LOCALIDAD, None)
        assert elegir_v0([OTRA_CALLE], 123, "CALLE QUE NO EXISTE 123") == (CALLE_DISTINTA, None)


class TestClasificarV1:
    def test_solo_esquina(self):
        assert clasificar_v1(V1_ESQUINA) == ESQUINA
        assert clasificar_v1(V1_OTRA) is None


class TestInterpretar:
    def test_puerta_exacta_con_coordenada(self):
        r = interpretar("JOSE PEDRO VARELA 1500", "Salto", "Salto", [EXACTA])
        assert (r["calidad"], r["lat"], r["lon"], r["dentro_de_uruguay"]) == (PUERTA_EXACTA, -31.39, -57.96, True)
        assert r["direccion_devuelta"] == "JOSE PEDRO VARELA 1500 SALTO"

    def test_otra_calle_no_trae_coordenada(self):
        r = interpretar("CALLE QUE NO EXISTE 123", "", "", [OTRA_CALLE])
        assert (r["calidad"], r["lat"], r["lon"]) == (CALLE_DISTINTA, None, None)

    def test_la_esquina_le_gana_al_centro_de_la_avenida(self):
        avenida = _v0("AVENIDA 18 DE JULIO", tipo=27, localidad="MONTEVIDEO")
        r = interpretar("18 DE JULIO Y EJIDO", "Montevideo", "Montevideo", [avenida], [V1_ESQUINA])
        assert (r["calidad"], r["lat"]) == (ESQUINA, -34.90)

    def test_la_puerta_le_gana_a_la_esquina(self):
        r = interpretar("JOSE PEDRO VARELA 1500 esq. X", "", "", [EXACTA], [V1_ESQUINA])
        assert r["calidad"] == PUERTA_EXACTA

    def test_v1_que_no_es_esquina_se_ignora(self):
        r = interpretar("ARTIGAS Y SOLARI", "", "", [CENTROIDE], [V1_OTRA])
        assert (r["calidad"], r["lat"]) == (LOCALIDAD, None)


class TestGeometria:
    def test_rectangulo_de_uruguay(self):
        assert dentro_de_uruguay(-31.4, -57.96)
        assert not dentro_de_uruguay(0.0, 0.0)
        assert dentro_de_uruguay(-30.0, -53.0) and dentro_de_uruguay(-35.0, -58.5)

    def test_un_grado_de_latitud(self):
        assert 110.0 < distancia_km(-31.0, -57.0, -32.0, -57.0) < 112.5


class TestUrls:
    def test_v0_codifica_utf8(self):
        url = url_v0("CONSTITUCIÓN 100", "Salto", "Salto")
        assert url.startswith("https://direcciones.ide.uy/api/v0/geocode/BusquedaDireccion?")
        assert "%C3%93" in url and " " not in url

    def test_v1_omite_lo_vacio(self):
        assert url_v1("ARTIGAS Y SOLARI").endswith("q=ARTIGAS+ESQ+SOLARI%2C+Uruguay")


class TestEsquinaParaV1:
    def test_y_se_pide_como_esq(self):
        """v1 no reconoce '18 DE JULIO Y EJIDO' como esquina y sí 'ESQ' (medido el 09/10/2026)."""
        assert "ESQ" in url_v1("18 DE JULIO Y EJIDO")
        assert "+Y+" not in url_v1("18 DE JULIO Y EJIDO")

    def test_una_palabra_que_empieza_con_esq_no_es_esquina(self):
        assert misma_calle("Esquema 100", "ESQUEMA")


class TestV1QueNoResponde:
    def test_el_resultado_de_v0_se_conserva(self, monkeypatch):
        from uydatos import ideuy

        avenida = _v0("AVENIDA 18 DE JULIO", tipo=27, localidad="MONTEVIDEO")

        def consultar(url):
            if "/v1/" in url:
                raise TimeoutError("The read operation timed out")
            return [avenida]

        monkeypatch.setattr(ideuy, "_consultar", consultar)
        r = ideuy.geocodificar("18 DE JULIO Y EJIDO", "Montevideo", "Montevideo")
        assert r["calidad"] == CALLE
        assert "v1" in r["aviso_de_la_api"]


class TestOrdenDeLasCalles:
    def test_si_un_orden_no_da_esquina_prueba_el_inverso(self, monkeypatch):
        """'18 DE JULIO ESQ EJIDO' devolvió [] y 'EJIDO ESQ 18 DE JULIO' la esquina (09/10/2026)."""
        from uydatos import ideuy

        pedidas = []

        def consultar(url):
            pedidas.append(url)
            if "/v0/" in url:
                return [_v0("AVENIDA 18 DE JULIO", tipo=27, localidad="MONTEVIDEO")]
            return [V1_ESQUINA] if "q=EJIDO+ESQ" in url else []

        monkeypatch.setattr(ideuy, "_consultar", consultar)
        r = ideuy.geocodificar("18 DE JULIO Y EJIDO", "Montevideo", "Montevideo")
        assert r["calidad"] == ESQUINA
        assert len(pedidas) == 3

    def test_calles_de_una_esquina(self):
        from uydatos.ideuy import calles_de_esquina

        assert calles_de_esquina("18 DE JULIO Y EJIDO") == ("18 DE JULIO", "EJIDO")
        assert calles_de_esquina("Artigas 691 esq. Solari") == ("Artigas 691", "Solari")
        assert calles_de_esquina("JOSE P. VARELA 1500") is None
