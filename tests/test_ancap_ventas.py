"""Tests del lector de cantidad de ventas de combustibles de ANCAP.

Fijan lo que puede romperse en silencio y dar un total creíble pero falso:

- **`TestDosUnidades`**: la columna `Unidad` mezcla `Miles de m3` con `Toneladas`. Sumar la columna
  sin separarlas pone 12.330 al lado de 264.027, y los dos números parecen plausibles.
- **`TestVentanaMovil`**: el archivo **no es la historia completa**: es una ventana de cinco años, y
  los huecos no son sólo el año en curso (medido: 2024 sin octubre, 2025 sin agosto a octubre). Un
  mes que no está no es un mes en cero, y el resumen declara cuáles faltan.
- **`TestSinonimosQueNoSeUnifican`**: `QUEROSENO` es de `BLANCOS` y `QUEROSENOS` de `SOLVENTES`.
  Parecen el error de tipeo del otro y son productos distintos.
- **`TestBandera`**: `B/E` y `B/N` parten el mismo producto; el total del mercado los suma juntos.
- **`TestCorrecciones`**: los negativos son correcciones de la fuente, se leen y se suman.
- **`TestRechazos`**: columnas, cantidad de campos, mes imposible, número ilegible, unidad vacía.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from uydatos.ancap_ventas import (
    AncapVentasInvalido,
    leer,
    resumen,
    serie_mensual,
)

ENCABEZADO = "Mercado;Mes;Anio;FamiliaDeProducto;LineaDeProducto;Bandera;CantidadCorregida;Unidad"


def _escribir(p: Path, filas: list[str]) -> None:
    p.write_text(ENCABEZADO + "\n" + "\n".join(filas) + "\n", encoding="utf-8-sig")


def _fila(
    mercado="INTERNO",
    mes="01",
    anio="2026",
    familia="BLANCOS",
    linea="GAS OIL",
    bandera="B/N",
    cantidad="1,5",
    unidad="Miles de m3",
) -> str:
    return f"{mercado};{mes};{anio};{familia};{linea};{bandera};{cantidad};{unidad}"


class TestDosUnidades:
    def test_no_se_suman_entre_si(self, tmp_path):
        """Medido el 10/10/26: 1.178 filas en `Miles de m3` y 22 en `Toneladas`."""
        f = tmp_path / "v.csv"
        _escribir(
            f,
            [
                _fila(cantidad="10", unidad="Miles de m3"),
                _fila(cantidad="20000", unidad="Toneladas", familia="COMBUSTIBLES SÓLIDOS", linea="PETCOKE"),
            ],
        )
        registros = leer(f)
        # La serie pide una unidad: la otra no entra.
        assert serie_mensual(registros, unidad="Miles de m3")[0]["cantidad"] == pytest.approx(10.0)
        assert serie_mensual(registros, unidad="Toneladas")[0]["cantidad"] == pytest.approx(20000.0)

    def test_el_resumen_las_declara_aparte(self, tmp_path):
        f = tmp_path / "v.csv"
        _escribir(
            f,
            [
                _fila(cantidad="10"),
                _fila(cantidad="20000", unidad="Toneladas", familia="COMBUSTIBLES SÓLIDOS", linea="PETCOKE"),
            ],
        )
        r = resumen(leer(f))
        assert r["unidades"] == {"Miles de m3": pytest.approx(10.0), "Toneladas": pytest.approx(20000.0)}

    def test_una_unidad_nueva_suma_en_su_renglon_y_no_rompe_el_archivo(self, tmp_path):
        """Como las monedas de `compras`: una unidad que no se midió no rechaza el archivo."""
        f = tmp_path / "v.csv"
        _escribir(f, [_fila(cantidad="10"), _fila(cantidad="7", unidad="Miles de litros")])
        r = resumen(leer(f))
        assert r["unidades"]["Miles de litros"] == pytest.approx(7.0)


class TestVentanaMovil:
    def test_el_resumen_declara_los_meses_que_faltan(self, tmp_path):
        """2024 sin octubre y 2025 sin agosto, setiembre ni octubre: el hueco no es el año en curso."""
        f = tmp_path / "v.csv"
        filas = [_fila(mes="09", anio="2024"), _fila(mes="11", anio="2024")]
        filas += [_fila(mes="07", anio="2025"), _fila(mes="11", anio="2025")]
        _escribir(f, filas)
        cobertura = resumen(leer(f))["cobertura"]
        assert cobertura[2024] == {"meses": 2, "faltan": [1, 2, 3, 4, 5, 6, 7, 8, 10, 12]}
        assert cobertura[2025] == {"meses": 2, "faltan": [1, 2, 3, 4, 5, 6, 8, 9, 10, 12]}

    def test_un_mes_ausente_no_es_un_cero(self, tmp_path):
        """La serie no inventa el mes que no vino: no aparece."""
        f = tmp_path / "v.csv"
        _escribir(f, [_fila(mes="01"), _fila(mes="03")])
        serie = serie_mensual(leer(f))
        assert [s["mes"] for s in serie] == [1, 3]

    def test_la_serie_viene_ordenada_por_anio_y_mes(self, tmp_path):
        f = tmp_path / "v.csv"
        _escribir(f, [_fila(mes="12", anio="2025"), _fila(mes="01", anio="2025"), _fila(mes="02", anio="2026")])
        serie = serie_mensual(leer(f))
        assert [(s["anio"], s["mes"]) for s in serie] == [(2025, 1), (2025, 12), (2026, 2)]


class TestSinonimosQueNoSeUnifican:
    def test_queroseno_y_querosenos_son_productos_distintos(self, tmp_path):
        """Uno es `BLANCOS` y el otro `SOLVENTES`: no se unifican por parecerse."""
        f = tmp_path / "v.csv"
        _escribir(
            f,
            [
                _fila(linea="QUEROSENO", familia="BLANCOS", cantidad="3"),
                _fila(linea="QUEROSENOS", familia="SOLVENTES", cantidad="5"),
            ],
        )
        registros = leer(f)
        assert serie_mensual(registros, linea="QUEROSENO")[0]["cantidad"] == pytest.approx(3.0)
        assert serie_mensual(registros, linea="QUEROSENOS")[0]["cantidad"] == pytest.approx(5.0)

    def test_fuel_oil_y_fuel_oil_int_tambien(self, tmp_path):
        f = tmp_path / "v.csv"
        _escribir(
            f,
            [
                _fila(linea="FUEL OIL", familia="NEGROS", cantidad="1"),
                _fila(linea="FUEL OIL INT.", familia="NEGROS", cantidad="2"),
            ],
        )
        assert len({r["linea"] for r in leer(f)}) == 2


class TestBandera:
    def test_el_total_del_mercado_suma_las_dos_banderas(self, tmp_path):
        """Medido: `Bunker` viene 195 `B/E` y 170 `B/N`; agrupar sin la bandera junta 168 filas."""
        f = tmp_path / "v.csv"
        _escribir(
            f,
            [
                _fila(mercado="Bunker", bandera="B/E", cantidad="4"),
                _fila(mercado="Bunker", bandera="B/N", cantidad="6"),
            ],
        )
        serie = serie_mensual(leer(f), mercado="Bunker")
        assert serie[0]["cantidad"] == pytest.approx(10.0)
        assert serie[0]["filas"] == 2

    def test_y_se_pueden_mirar_por_separado(self, tmp_path):
        f = tmp_path / "v.csv"
        _escribir(f, [_fila(bandera="B/E", cantidad="4"), _fila(bandera="B/N", cantidad="6")])
        de_bandera_extranjera = [r["cantidad"] for r in leer(f) if r["bandera"] == "B/E"]
        assert de_bandera_extranjera == [pytest.approx(4.0)]


class TestCorrecciones:
    def test_los_negativos_se_leen_y_se_suman(self, tmp_path):
        """Medido: 6 filas de 1.200, la más negativa `-0,160273`. Son correcciones, no errores."""
        f = tmp_path / "v.csv"
        _escribir(f, [_fila(cantidad="10"), _fila(cantidad="-0,160273")])
        r = resumen(leer(f))
        assert r["unidades"]["Miles de m3"] == pytest.approx(9.839727)
        assert r["correcciones_negativas"] == 1

    def test_la_coma_es_decimal_y_el_punto_de_miles(self, tmp_path):
        f = tmp_path / "v.csv"
        _escribir(f, [_fila(cantidad="1.234,5")])
        assert leer(f)[0]["cantidad"] == pytest.approx(1234.5)


class TestNulos:
    def test_una_cantidad_vacia_es_nula_y_no_cero(self, tmp_path):
        f = tmp_path / "v.csv"
        _escribir(f, [_fila(cantidad="")])
        registros = leer(f)
        assert registros[0]["cantidad"] is None
        assert resumen(registros)["nulos"] == 1
        assert serie_mensual(registros) == []
        assert resumen(registros)["unidades"] == {}


class TestRechazos:
    def test_columnas_cambiadas(self, tmp_path):
        f = tmp_path / "v.csv"
        f.write_text("Mercado;Mes;Anio\nINTERNO;01;2026\n", encoding="utf-8-sig")
        with pytest.raises(AncapVentasInvalido, match="columnas"):
            leer(f)

    def test_una_fila_con_menos_campos(self, tmp_path):
        f = tmp_path / "v.csv"
        f.write_text(ENCABEZADO + "\nINTERNO;01;2026;BLANCOS\n", encoding="utf-8-sig")
        with pytest.raises(AncapVentasInvalido, match="columnas"):
            leer(f)

    def test_un_mes_imposible(self, tmp_path):
        f = tmp_path / "v.csv"
        _escribir(f, [_fila(mes="13")])
        with pytest.raises(AncapVentasInvalido, match="mes"):
            leer(f)

    def test_una_cantidad_ilegible(self, tmp_path):
        f = tmp_path / "v.csv"
        _escribir(f, [_fila(cantidad="abc")])
        with pytest.raises(AncapVentasInvalido, match="cantidad"):
            leer(f)

    def test_una_fila_sin_unidad(self, tmp_path):
        f = tmp_path / "v.csv"
        f.write_text(ENCABEZADO + "\nINTERNO;01;2026;BLANCOS;GAS OIL;B/N;1,5;\n", encoding="utf-8-sig")
        with pytest.raises(AncapVentasInvalido, match="unidad"):
            leer(f)

    def test_archivo_sin_filas(self, tmp_path):
        f = tmp_path / "v.csv"
        _escribir(f, [])
        with pytest.raises(AncapVentasInvalido, match="sin filas"):
            leer(f)

    def test_archivo_inexistente(self, tmp_path):
        with pytest.raises(AncapVentasInvalido, match="no está"):
            leer(tmp_path / "no_existe.csv")

    def test_las_filas_en_blanco_se_saltean(self, tmp_path):
        f = tmp_path / "v.csv"
        _escribir(f, [_fila(cantidad="1"), "", "   ", _fila(cantidad="2")])
        assert len(leer(f)) == 2


class TestUrlVigente:
    """El 12/10/26 ANCAP republicó el dataset y el id del recurso cambió: la URL fija dio 404."""

    NOMBRE = "datos-de-cantidad-de-ventas-de-combustibles.csv"

    def test_elige_el_csv_de_datos_por_nombre(self, monkeypatch):
        from uydatos import ancap_ventas, catalogo

        vigente = f"https://x/resource/NUEVO/download/{self.NOMBRE}"
        monkeypatch.setattr(
            catalogo,
            "recursos",
            lambda d: [
                {"url": "https://x/resource/a/download/metadatos-cantidad-de-ventas-de-combustibles.json"},
                {"url": vigente},
                {"url": f"https://x/resource/b/download/{self.NOMBRE[:-3]}xml"},
            ],
        )
        assert ancap_ventas.url_vigente() == vigente

    def test_sin_catalogo_cae_a_la_ultima_conocida(self, monkeypatch):
        from uydatos import ancap_ventas, catalogo

        def caido(_):
            raise OSError("sin red")

        monkeypatch.setattr(catalogo, "recursos", caido)
        assert ancap_ventas.url_vigente() == ancap_ventas.URL_CSV

    def test_dos_csv_se_rechaza(self, monkeypatch):
        import pytest

        from uydatos import ancap_ventas, catalogo
        from uydatos.ancap_ventas import AncapVentasInvalido

        monkeypatch.setattr(
            catalogo, "recursos", lambda d: [{"url": f"https://x/{i}/download/{self.NOMBRE}"} for i in range(2)]
        )
        with pytest.raises(AncapVentasInvalido, match="2 recursos"):
            ancap_ventas.url_vigente()
