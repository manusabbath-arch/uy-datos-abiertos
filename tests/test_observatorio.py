"""El lector de las páginas de indicador del Observatorio Social, con páginas armadas como las reales."""

from __future__ import annotations

import html
import json

import pytest

from uydatos import observatorio as o


def _pagina(
    encabezado: list[str],
    filas: list[list[str]],
    filtros: dict | None,
    *,
    unidad: str = "Por cien",
    fin: int = 2024,
    opciones: list[str] = (),
) -> str:
    """Una página con la forma medida: título, descripción, filtros, una tabla y la ficha."""
    th = "".join(f"<th>{c}</th>" for c in encabezado)
    trs = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in f) + "</tr>" for f in filas)
    form = ""
    if filtros is not None:
        valor = html.escape(json.dumps({**filtros, "style": "line"}))
        form = f'<input name="current_filters" value="{valor}" />'
        form += "".join(f'<input name="filter_options" value="{x}" />' for x in opciones)
    return (
        "<html><head><title>Tasa de algo. Total país | MIDES</title>"
        '<meta name="description" content="Proporción de algo." /></head><body>'
        f"{form}<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>"
        "<h3>Forma de cálculo</h3><p>(a/b)*100</p><h3>Fuente</h3><p class='fuente'>INE Encuesta Continua de Hogares</p>"
        "<h3>Frecuencia</h3><p>Anual</p><h3>Período</h3><ul><li>Año de inicio:\n2006</li>"
        f"<li>Año de fin:\n{fin}</li></ul><h3>Unidad de observación</h3><p>{unidad}</p>"
        '<h3>Etiquetas</h3><div class="Tags">x</div><a>Reportar errores o sugerir mejoras</a><footer></footer>'
        "</body></html>"
    )


def _opts(*xs: str) -> dict:
    return {x: x for x in xs}


class TestLeerPagina:
    def test_lee_la_ficha_y_los_datos(self):
        r = o.leer_pagina(
            _pagina(
                ["Sexo", "2023", "2024"],
                [["Mujeres", "55,9", "56,1"], ["Varones", "1.201", "-"]],
                {"Sexo": _opts("Mujeres", "Varones"), "Año": _opts("2023", "2024")},
            )
        )
        assert r["titulo"] == "Tasa de algo. Total país"
        assert r["descripcion"] == "Proporción de algo."
        assert (r["unidad"], r["fuente"], r["calculo"]) == ("Por cien", "INE Encuesta Continua de Hogares", "(a/b)*100")
        assert r["periodo_ficha"] == {"inicio": 2006, "fin": 2024}
        assert r["dimensiones"] == ["Sexo"] and r["periodos"] == ["2023", "2024"]
        assert r["filas"][0]["valores"] == {"2023": 55.9, "2024": 56.1}
        # punto de miles, y el guion es un nulo, no un cero
        assert r["filas"][1]["valores"] == {"2023": 1201.0, "2024": None}
        assert r["avisos"] == [] and r["parcial"] is False

    def test_la_unidad_no_arrastra_el_enlace_que_le_sigue(self):
        r = o.leer_pagina(_pagina(["Sexo", "2024"], [["Mujeres", "1"]], {"Sexo": {}, "Año": _opts("2024")}))
        assert r["unidad"] == "Por cien"

    def test_el_punto_suelto_tambien_es_sin_dato(self):
        r = o.leer_pagina(
            _pagina(["X", "2019", "2020"], [["Porcentaje", "5", "."]], {"X": {}, "Año": _opts("2019", "2020")})
        )
        assert r["filas"][0]["valores"]["2020"] is None

    def test_la_pagina_sin_filtros_es_del_formato_viejo_y_se_rechaza(self):
        with pytest.raises(o.ObservatorioInvalido, match="formato viejo"):
            o.leer_pagina(_pagina(["País", "2011"], [["Argentina", "16.8"]], None))

    def test_un_numero_con_punto_decimal_se_rechaza(self):
        with pytest.raises(o.ObservatorioInvalido, match="'16.8'"):
            o.leer_pagina(
                _pagina(
                    ["País", "2011"], [["Brasil", "15,4"], ["Argentina", "16.8"]], {"País": {}, "Año": _opts("2011")}
                )
            )

    def test_basura_en_una_celda_se_rechaza_mostrandola(self):
        with pytest.raises(o.ObservatorioInvalido, match="'@'"):
            o.leer_pagina(
                _pagina(["X", "2012"], [["Varones", "4,7"], ["Mujeres", "@"]], {"X": {}, "Año": _opts("2012")})
            )

    def test_una_dimension_sin_filtro_y_metida_entre_los_anios(self):
        """Medido: «Pobreza» figura entre las opciones del filtro de años y no tiene filtro propio."""
        r = o.leer_pagina(
            _pagina(
                ["Sexo", "Pobreza", "2023", "2024"],
                [["Mujeres", "Pobre", "35,6", "35,5"], ["Mujeres", "Total", "50", "51"]],
                {"Sexo": _opts("Mujeres"), "Año": _opts("Pobreza", "2023", "2024")},
                fin=2023,
            )
        )
        assert r["dimensiones"] == ["Sexo", "Pobreza"] and r["periodos"] == ["2023", "2024"]
        assert any("filas de total" in a for a in r["avisos"])
        assert any("termina en 2023 y la tabla llega a 2024" in a for a in r["avisos"])

    def test_las_columnas_sin_encabezado_con_ceros_se_descartan(self):
        r = o.leer_pagina(
            _pagina(
                ["Departamento", "dic-2025", "", ""],
                [["Artigas", "156", "0", "0"]],
                {"Departamento": {}, "Mes": _opts("dic-2025")},
            )
        )
        assert r["periodos"] == ["dic-2025"] and r["columnas_descartadas"] == 2
        assert r["filas"][0]["valores"] == {"dic-2025": 156.0}

    def test_una_columna_sin_encabezado_con_un_valor_se_rechaza(self):
        with pytest.raises(o.ObservatorioInvalido, match="sin encabezado"):
            o.leer_pagina(_pagina(["D", "2025", ""], [["Artigas", "156", "7"]], {"D": {}, "Año": _opts("2025")}))

    def test_el_mapa_muestra_un_anio_y_se_marca_parcial(self):
        r = o.leer_pagina(
            _pagina(
                ["Departamento", "2023"],
                [["Salto", "12,8"], ["Total", "10,1"]],
                {"Departamento": _opts("Salto", "Total"), "Año": _opts("2023")},
                fin=2023,
                opciones=["2006", "2007", "2023"],
            )
        )
        assert r["parcial"] is True and r["periodos_disponibles"] == ["2006", "2007", "2023"]
        assert any("muestra sólo 2023" in a for a in r["avisos"])

    def test_dos_tablas_o_celdas_combinadas_no_se_adivinan(self):
        p = _pagina(["X", "2024"], [["a", "1"]], {"X": {}, "Año": _opts("2024")})
        with pytest.raises(o.ObservatorioInvalido, match="2 tablas"):
            o.leer_pagina(p.replace("</table>", "</table><table></table>", 1))
        with pytest.raises(o.ObservatorioInvalido, match="combina celdas"):
            o.leer_pagina(p.replace("<td>a</td>", '<td rowspan="2">a</td>'))


class TestLista:
    INDICE = (
        '<?xml version="1.0"?><sitemapindex><sitemap>\n  <loc>https://x/sitemap.xml?page=1</loc>\n'
        "</sitemap><sitemap><loc>https://x/sitemap.xml?page=2</loc></sitemap></sitemapindex>"
    )

    def test_el_indice_del_sitemap(self):
        assert o.paginas_del_sitemap(self.INDICE) == ["https://x/sitemap.xml?page=1", "https://x/sitemap.xml?page=2"]

    def test_solo_las_paginas_de_indicador(self):
        xml = f"<url><loc>{o.PREFIJO}tasa-empleo-total-pais</loc></url><url><loc>{o.BASE}/noticias/x</loc></url>"
        assert o.indicadores_del_sitemap(xml) == ["tasa-empleo-total-pais"]

    def test_buscar_exige_todas_las_palabras_sin_tildes_y_por_raiz(self):
        slugs = [
            "porcentaje-personas-situacion-pobreza-segun-departamento-total-pais",
            "porcentaje-personas-situacion-pobreza-total-pais",
            "tasa-empleo-segun-departamento-total-pais",
        ]
        assert o.buscar(slugs, "pobreza departamentos") == [slugs[0]]
        assert o.buscar(slugs, "Situación") == [slugs[1], slugs[0]]

    def test_buscar_sin_palabras_se_rechaza(self):
        with pytest.raises(o.ObservatorioInvalido):
            o.buscar(["a"], "de")

    def test_url_de_un_nombre_o_de_la_url(self):
        assert o.url_de("tasa-empleo-total-pais") == o.PREFIJO + "tasa-empleo-total-pais"
        assert o.url_de(o.PREFIJO + "tasa-empleo-total-pais/") == o.PREFIJO + "tasa-empleo-total-pais"
        with pytest.raises(o.ObservatorioInvalido):
            o.url_de("https://otro.sitio/x")

    def test_el_indice_vacio_se_rechaza(self, monkeypatch):
        monkeypatch.setattr(o.red, "pedir", lambda url: b"<sitemapindex></sitemapindex>")
        with pytest.raises(o.ObservatorioInvalido, match="no trae páginas"):
            o.indice()

    def test_un_indicador_que_no_existe_lo_dice(self, monkeypatch):
        def pedir(url):
            raise OSError(f"{url}: el servidor respondio 404 Not Found")

        monkeypatch.setattr(o.red, "pedir", pedir)
        with pytest.raises(o.ObservatorioInvalido, match="no existe"):
            o.leer("no-existe-esto")
