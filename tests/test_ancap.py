"""Tests del lector de precios de combustible de ANCAP (Poder Ejecutivo).

Fijan lo que puede romperse en silencio y dar una serie creible pero falsa:

- **`TestColumnasInvertidas`**: el encabezado dice `Unidad` y `Valor`, pero **`Unidad` trae el
  numero y `Valor` la unidad de medida** (medido el 04/10/26: `'58,68'` y `'$/lt'`). El lector
  tiene que nombrarlas por lo que SON, y rechazar si la fuente las da vuelta.
- **`TestPublicacionesApiladas`**: el archivo **NO es una serie**, es un log de publicaciones
  acumulativas: el precio de 2022-01 aparece **29 veces**. `serie_mensual()` tiene que
  deduplicar a una fila por (producto, ano, mes); contar o promediar las publicaciones mide la
  cantidad de publicaciones, no el precio. Es el defecto de la hoja "Todos".
- **`TestSinCotizacion`**: `S/C` es *sin cotizacion*: un nulo, no un cero. Y un mes que
  alguna vez tuvo precio no se pierde porque una publicacion posterior diga `S/C`.
- **`TestDecimal`**: el archivo usa **coma decimal** (`58,68`). Un `float(valor)` sin mas lee
  `58` y no avisa.
- **`TestBomDoble`**: el archivo trae **dos BOM**, asi que `utf-8-sig` no alcanza.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from uydatos.ancap import (
    AncapInvalido,
    leer_publicaciones,
    precio_del_mes,
    serie_mensual,
)

ENCABEZADO = "Año;Mes;Producto;Unidad;Valor"
BOM_DOBLE = "\ufeff\ufeff"


def _escribir(p: Path, filas: list[str]) -> None:
    p.write_text(BOM_DOBLE + ENCABEZADO + "\n" + "\n".join(filas) + "\n", encoding="utf-8-sig")


class TestColumnasInvertidas:
    def test_la_columna_unidad_trae_el_numero(self, tmp_path):
        """Medido el 04/10/26: `Unidad` es el precio y `Valor` la unidad de medida."""
        f = tmp_path / "a.csv"
        _escribir(f, ["2026;7;GASOIL 50-S *;58,68;$/lt"])
        serie = serie_mensual(leer_publicaciones(f))
        assert serie[0]["precio"] == pytest.approx(58.68)
        assert serie[0]["unidad"] == "$/lt"

    def test_si_la_fuente_las_da_vuelta_se_rechaza(self, tmp_path):
        """Si `Valor` trae un numero, la fuente invirtio las columnas: se rechaza."""
        f = tmp_path / "a.csv"
        _escribir(f, ["2026;7;GASOIL 50-S *;$/lt;58,68"])
        with pytest.raises(AncapInvalido, match="unidad"):
            leer_publicaciones(f)


class TestPublicacionesApiladas:
    def _apilado(self, tmp_path):
        """Tres publicaciones del mismo ano: ene (1 mes), feb (2), mar (3)."""
        f = tmp_path / "a.csv"
        _escribir(
            f,
            [
                "2026;1;GASOIL 50-S *;48,90;$/lt",
                "2026;1;GASOIL 50-S *;48,90;$/lt",
                "2026;2;GASOIL 50-S *;50,00;$/lt",
                "2026;1;GASOIL 50-S *;48,90;$/lt",
                "2026;2;GASOIL 50-S *;50,00;$/lt",
                "2026;3;GASOIL 50-S *;52,00;$/lt",
            ],
        )
        return f

    def test_las_filas_crudas_son_las_publicaciones(self, tmp_path):
        assert len(leer_publicaciones(self._apilado(tmp_path))) == 6

    def test_la_serie_deduplica_a_una_fila_por_mes(self, tmp_path):
        serie = serie_mensual(leer_publicaciones(self._apilado(tmp_path)))
        assert len(serie) == 3
        assert [s["mes"] for s in serie] == [1, 2, 3]

    def test_el_precio_de_un_mes_no_se_promedia_entre_publicaciones(self, tmp_path):
        """Promediar daria 48,90 (el mismo) — pero con dos precios distintos no."""
        f = tmp_path / "a.csv"
        _escribir(
            f,
            [
                "2026;1;GASOIL 50-S *;48,90;$/lt",
                "2026;2;GASOIL 50-S *;50,00;$/lt",
                "2026;1;GASOIL 50-S *;49,90;$/lt",
                "2026;2;GASOIL 50-S *;50,00;$/lt",
            ],
        )
        serie = serie_mensual(leer_publicaciones(f))
        # El ultimo valor de ese mes gana: no se suma ni se promedia.
        assert precio_del_mes(serie, "GASOIL 50-S *", 2026, 1) == pytest.approx(49.90)


class TestSinCotizacion:
    def test_sin_cotizacion_no_es_cero(self, tmp_path):
        f = tmp_path / "a.csv"
        _escribir(f, ["2026;8;GASOIL 50-S *;S/C;S/C"])
        serie = serie_mensual(leer_publicaciones(f))
        assert serie[0]["precio"] is None
        assert serie[0]["unidad"] == ""

    def test_un_precio_que_existio_no_se_pierde_por_un_sc_posterior(self, tmp_path):
        """Medido: 2 combinaciones (2022-10, 2023-08) pasaron de precio a `S/C`."""
        f = tmp_path / "a.csv"
        _escribir(
            f,
            [
                "2022;10;GASOIL 50-S *;64,99;$/lt",
                "2022;10;GASOIL 50-S *;S/C;S/C",
            ],
        )
        serie = serie_mensual(leer_publicaciones(f))
        assert precio_del_mes(serie, "GASOIL 50-S *", 2022, 10) == pytest.approx(64.99)


class TestDecimal:
    def test_la_coma_es_decimal_no_separador_de_miles(self, tmp_path):
        """`58,68` son 58,68. Un `float()` pelado lee 58 y no avisa."""
        f = tmp_path / "a.csv"
        _escribir(f, ["2026;7;GASOIL 50-S *;58,68;$/lt"])
        assert serie_mensual(leer_publicaciones(f))[0]["precio"] == pytest.approx(58.68)

    def test_el_punto_es_separador_de_miles(self, tmp_path):
        f = tmp_path / "a.csv"
        _escribir(f, ["2026;7;GASOIL 50-S *;1.234,50;$/lt"])
        assert serie_mensual(leer_publicaciones(f))[0]["precio"] == pytest.approx(1234.50)


class TestRechazos:
    def test_columnas_cambiadas(self, tmp_path):
        f = tmp_path / "a.csv"
        f.write_text(BOM_DOBLE + "ano;mes;p;u;v\n2026;7;X;58,68;$/lt\n", encoding="utf-8-sig")
        with pytest.raises(AncapInvalido, match="columnas"):
            leer_publicaciones(f)

    def test_archivo_sin_filas(self, tmp_path):
        f = tmp_path / "a.csv"
        _escribir(f, [])
        with pytest.raises(AncapInvalido, match="sin filas"):
            leer_publicaciones(f)

    def test_archivo_inexistente(self, tmp_path):
        with pytest.raises(AncapInvalido, match="no está"):
            leer_publicaciones(tmp_path / "no_existe.csv")

    def test_precio_ilegible(self, tmp_path):
        f = tmp_path / "a.csv"
        _escribir(f, ["2026;7;GASOIL 50-S *;abc;$/lt"])
        with pytest.raises(AncapInvalido, match="precio"):
            leer_publicaciones(f)


class TestUrlVigente:
    """El 12/10/26 ANCAP republicó el dataset y el id del recurso cambió: la URL fija dio 404 en la
    corrida semanal. `descargar()` tiene que preguntar al catálogo, no recordar un id."""

    @staticmethod
    def _recursos(*urls):
        return [{"formato": "CSV", "url": u} for u in urls]

    def test_elige_el_csv_de_datos_por_nombre(self, monkeypatch):
        from uydatos import ancap, catalogo

        vigente = "https://x/resource/NUEVO/download/datos-de-precios-de-combustibles.csv"
        monkeypatch.setattr(
            catalogo,
            "recursos",
            lambda d: self._recursos(
                "https://x/resource/a/download/metadatos-de-precios-de-combustibles.json",
                vigente,
                "https://x/resource/b/download/datos-de-precios-de-combustibles.xml",
            ),
        )
        assert ancap.url_vigente() == vigente

    def test_descargar_usa_la_url_vigente(self, monkeypatch, tmp_path):
        from uydatos import ancap, catalogo, red

        vigente = "https://x/resource/NUEVO/download/datos-de-precios-de-combustibles.csv"
        monkeypatch.setattr(catalogo, "recursos", lambda d: self._recursos(vigente))
        pedidas = []
        monkeypatch.setattr(red, "bajar", lambda url, destino: pedidas.append(url) or destino)
        ancap.descargar(tmp_path / "a.csv")
        assert pedidas == [vigente]

    def test_una_url_explicita_no_pregunta_al_catalogo(self, monkeypatch, tmp_path):
        from uydatos import ancap, catalogo, red

        monkeypatch.setattr(catalogo, "recursos", lambda d: pytest.fail("no debia consultar el catalogo"))
        pedidas = []
        monkeypatch.setattr(red, "bajar", lambda url, destino: pedidas.append(url) or destino)
        ancap.descargar(tmp_path / "a.csv", url="https://x/y.csv")
        assert pedidas == ["https://x/y.csv"]

    def test_sin_catalogo_cae_a_la_ultima_conocida(self, monkeypatch):
        from uydatos import ancap, catalogo

        def caido(_):
            raise OSError("sin red")

        monkeypatch.setattr(catalogo, "recursos", caido)
        assert ancap.url_vigente() == ancap.URL_CSV

    @pytest.mark.parametrize("cuantos", [0, 2])
    def test_cero_o_dos_csv_se_rechaza(self, monkeypatch, cuantos):
        from uydatos import ancap, catalogo

        u = "https://x/resource/{}/download/datos-de-precios-de-combustibles.csv"
        monkeypatch.setattr(catalogo, "recursos", lambda d: self._recursos(*[u.format(i) for i in range(cuantos)]))
        with pytest.raises(AncapInvalido, match=f"{cuantos} recursos"):
            ancap.url_vigente()
