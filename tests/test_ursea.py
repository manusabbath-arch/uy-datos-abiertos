"""El PPI de URSEA, sus componentes, el ex planta de ANCAP y la comparación, con archivos armados."""

from __future__ import annotations

import pytest

from uydatos import ursea as u

ENCABEZADO_PPI = ",".join(u.COLUMNAS_PPI)


def _fila_ppi(inicio: str, fin: str, super_ag: float = 30.0, gasoil_ag: float = 40.0) -> str:
    valores = {c: "1" for c in u.COLUMNAS_PPI[2:]}
    valores.update({"Super_ExP_AC": str(super_ag), "Gasoil50S_ExP_AC": str(gasoil_ag), "FuelP_ExP": "99"})
    return ",".join([inicio, fin] + [valores[c] for c in u.COLUMNAS_PPI[2:]])


@pytest.fixture
def ppi(tmp_path):
    p = tmp_path / "ppi.csv"
    p.write_text(
        "\n".join(
            [
                ENCABEZADO_PPI,
                _fila_ppi("2026-06-26", "2026-07-25", 35.7, 37.05),
                _fila_ppi("2022-12-26", "2022-12-25"),  # la ventana imposible, medida
                _fila_ppi("2026-07-26", "2026-08-25", 37.04, 39.85),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return p


@pytest.fixture
def ex_planta(tmp_path):
    p = tmp_path / "ex.csv"
    p.write_text(
        "\ufeffAño-Mes;Producto;Unidad;PrecioExPlantaUYU\r\n"
        "2026-08;Gasolina Super 95;$/lt;37,98\r\n"
        "2026-08;Gasoil 50-S;$/lt;34,92\r\n"
        "\r\n"
        "202,608;Gasolina Super 95;$/lt;37,98\r\n"  # la misma fila, con la fecha de miles
        "202608;Gasoil 50-S;$/lt;34,92\r\n"
        "2024-01;Supergas A Granel;$/kg;-26,93\r\n"
        "2024-01;Supergas A Granel;$/kg;0\r\n"
        "2026-07;GLP;$/kg;40,05\r\n",
        encoding="utf-8",
    )
    return p


class TestPpi:
    def test_la_ventana_rige_el_mes_siguiente_y_la_imposible_se_descarta(self, ppi):
        r = u.leer_ppi(ppi)
        assert r["descartadas"] == [{"fila": 3, "inicio": "2022-12-26", "fin": "2022-12-25"}]
        vig = sorted({f["vigencia"] for f in r["filas"]})
        assert vig == ["2026-08", "2026-09"]
        super95 = next(f for f in r["filas"] if f["producto"] == "Gasolina Super 95" and f["vigencia"] == "2026-09")
        assert super95["sin_impuestos_con_agro"] == 37.04 and super95["dias"] == 31

    def test_fuel_pesado_con_impuestos_sale_de_la_columna_que_dice_ex_planta(self, ppi):
        fp = next(f for f in u.leer_ppi(ppi)["filas"] if f["producto"] == "Fuel Oil Pesado")
        assert fp["con_impuestos"] == 99.0 and fp["sin_impuestos_con_agro"] is None

    def test_el_modelo_viejo_con_fechas_d_m_aaaa_se_rechaza(self, tmp_path):
        p = tmp_path / "viejo.csv"
        p.write_text(ENCABEZADO_PPI + "\n" + _fila_ppi("1/10/2020", "31/10/2020") + "\n", encoding="utf-8")
        with pytest.raises(u.UrseaInvalido, match="AAAA-MM-DD"):
            u.leer_ppi(p)

    def test_dos_ventanas_con_la_misma_vigencia_se_rechazan(self, tmp_path):
        p = tmp_path / "dos.csv"
        filas = [ENCABEZADO_PPI, _fila_ppi("2026-06-26", "2026-07-25"), _fila_ppi("2026-07-01", "2026-07-20")]
        p.write_text("\n".join(filas) + "\n", encoding="utf-8")
        with pytest.raises(u.UrseaInvalido, match="ya rige en 2026-08"):
            u.leer_ppi(p)

    def test_otras_columnas_se_rechazan(self, tmp_path):
        p = tmp_path / "otras.csv"
        p.write_text("Inicio,Fin,X\n2026-01-01,2026-01-31,1\n", encoding="utf-8")
        with pytest.raises(u.UrseaInvalido, match="columnas"):
            u.leer_ppi(p)


class TestComponentes:
    COLS = (
        "producto,fecha_cierre,fecha_vigencia,subtotal_3_precio_ex_planta_con_biocombustible,"
        "total_precio_ex_planta_1,tipo_cambio_promedio,total_precio_ex_planta_2\n"
    )

    def test_la_vigencia_publicada_distinta_se_declara(self, tmp_path):
        p = tmp_path / "c.csv"
        p.write_text(
            self.COLS
            + "Gas Oil 50S,2026-08-25,2026-09-01,1131.35,1475.74,40.25,59.39\n"
            + "Gas Oil 10S,2026-08-25,2026-08-01,1132.21,1476.79,40.25,59.43\n",
            encoding="utf-8",
        )
        filas = u.leer_componentes(p)
        assert [(f["vigencia"], f["vigencia_publicada"]) for f in filas] == [
            ("2026-09", "2026-09"),
            ("2026-09", "2026-08"),
        ]

    def test_un_total_que_no_cierra_con_el_tipo_de_cambio_se_rechaza(self, tmp_path):
        p = tmp_path / "c.csv"
        p.write_text(self.COLS + "GLP,2026-08-25,2026-09-01,1,736.76,40.25,31.00\n", encoding="utf-8")
        with pytest.raises(u.UrseaInvalido, match="no da 31.0"):
            u.leer_componentes(p)


class TestExPlanta:
    def test_tres_formatos_de_fecha_y_las_repeticiones_se_unen(self, ex_planta):
        r = u.leer_ex_planta(ex_planta)
        assert r["precios"][("2026-08", "Gasoil 50-S")] == {"valor": 34.92, "unidad": "$/lt"}
        assert r["filas"] == 7 and r["repetidas"] == 2

    def test_dos_valores_distintos_quedan_en_nulo_y_se_listan(self, ex_planta):
        r = u.leer_ex_planta(ex_planta)
        assert r["precios"][("2024-01", "Supergas A Granel")]["valor"] is None
        assert r["conflictos"] == [{"mes": "2024-01", "producto": "Supergas A Granel", "valores": [-26.93, 0.0]}]

    def test_un_mes_imposible_se_rechaza(self, tmp_path):
        p = tmp_path / "e.csv"
        p.write_text("Año-Mes;Producto;Unidad;PrecioExPlantaUYU\n202613;Gasoil 50-S;$/lt;1\n", encoding="utf-8")
        with pytest.raises(u.UrseaInvalido, match="año-mes"):
            u.leer_ex_planta(p)


class TestComparar:
    def test_ancap_contra_el_ppi_del_mes_de_vigencia(self, ppi, ex_planta):
        c = u.comparar(u.leer_ppi(ppi), u.leer_ex_planta(ex_planta), "Gasoil 50-S")
        # sólo agosto: setiembre no tiene precio de ANCAP y no se rellena
        assert c == [
            {"mes": "2026-08", "ancap_ex_planta": 34.92, "ppi": 37.05, "diferencia": -2.13, "diferencia_pct": -5.7}
        ]

    def test_el_glp_no_se_compara(self, ppi, ex_planta):
        with pytest.raises(u.UrseaInvalido, match="no se compara"):
            u.comparar(u.leer_ppi(ppi), u.leer_ex_planta(ex_planta), "GLP")

    def test_url_de_elige_por_nombre_de_archivo(self):
        recursos = [{"url": "https://x/a/ppi_pe.csv"}, {"url": "https://x/b/ppi_da_nuevo.csv"}]
        assert u.url_de(recursos, "ppi_da_nuevo.csv") == "https://x/b/ppi_da_nuevo.csv"
        with pytest.raises(u.UrseaInvalido):
            u.url_de(recursos, "no_esta.csv")
