"""El sello que cierra un informe: fuente, cuando se bajo, sha256 y cuantas filas."""

from __future__ import annotations

from datetime import datetime

from uydatos import procedencia


class TestSha256:
    def test_calcula_el_sha256_de_un_archivo(self, tmp_path):
        ruta = tmp_path / "x.csv"
        ruta.write_bytes(b"a;b\n1;2\n")
        assert procedencia.sha256(ruta) == "403bea5152c251c5bc7ef420d824d191605723f99392e83a0549ad58c6d46291"


class TestSello:
    def test_toma_la_fecha_de_modificacion_si_no_se_le_pasa_una(self, tmp_path):
        ruta = tmp_path / "x.csv"
        ruta.write_bytes(b"1")
        s = procedencia.sello("BCU", ruta=ruta)
        assert s["fuente"] == "BCU"
        assert s["bytes"] == 1
        assert len(s["sha256"]) == 64
        datetime.fromisoformat(s["bajado"])

    def test_una_fecha_explicita_gana_sobre_la_del_archivo(self, tmp_path):
        ruta = tmp_path / "x.csv"
        ruta.write_bytes(b"1")
        s = procedencia.sello("BCU", ruta=ruta, bajado=datetime(2026, 10, 9, 22, 41))
        assert s["bajado"] == "2026-10-09T22:41"

    def test_un_archivo_que_no_existe_no_rompe_el_sello(self, tmp_path):
        s = procedencia.sello("BCU", ruta=tmp_path / "no-esta.csv")
        assert s["sha256"] is None and s["bytes"] is None

    def test_sin_archivo_el_sello_sirve_para_una_fuente_en_vivo(self):
        s = procedencia.sello("IDE.uy", url="https://direcciones.ide.uy/api/v0/geocode")
        assert s["sha256"] is None and s["bytes"] is None and s["url"].startswith("https://")

    def test_la_linea_cierra_un_informe(self, tmp_path):
        ruta = tmp_path / "x.csv"
        ruta.write_bytes(b"1")
        linea = procedencia.como_linea(procedencia.sello("BCU", ruta=ruta, filas=332070))
        assert "BCU" in linea and "332.070 filas" in linea and "sha256:" in linea
