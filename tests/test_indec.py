"""Tests del lector del IPC argentino (API de series de datos.gob.ar).

Fijan las dos trampas que el documento de investigacion advierte:

- **`TestSerieViva`**: la API sirve series **base 2003/2008 discontinuadas en 2013** sin
  avisar. El lector declara el id vivo como constante y rechaza cualquier otro; pedir la
  serie muerta no puede devolver un indice que se lea como actual.
- **`TestNoEsInflacion`**: un **indice** no es una **inflacion**. El lector devuelve el valor
  del indice y su `meta`; no lo convierte en inflacion mensual por su cuenta. Convertirlo es
  una decision, no una lectura.
- **`TestFixtures`**: los tests leen un recorte real de la respuesta de la API, **no la red**. Un test que sale a
  la red no es una guarda, es una dependencia.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from uydatos.indec import (
    ID_GBA,
    ID_NACIONAL_VIVA,
    IpcInvalido,
    leer,
)

FUENTE = Path(__file__).parent / "fixtures" / "indec_ipc_nacional_2016-12_a_2017-12.json"


class TestSerieViva:
    def test_el_id_vivo_es_el_de_base_diciembre_2016(self):
        assert ID_NACIONAL_VIVA == "148.3_INIVELNAL_DICI_M_26"

    def test_gba_no_es_la_nacional(self):
        """GBA != Concordia: son dos ids distintos y el lector no los confunde."""
        assert ID_GBA != ID_NACIONAL_VIVA

    def test_un_id_muerto_se_rechaza(self, tmp_path):
        """Base 2003/2008: discontinuada en 2013 y la API la sigue sirviendo."""
        f = tmp_path / "m.json"
        f.write_text(json.dumps({"data": [], "count": 0, "meta": []}), encoding="utf-8")
        with pytest.raises(IpcInvalido, match="base"):
            leer(f, id_serie="145.3_INGNACUAL_DICI_M_48")


class TestNoEsInflacion:
    def test_el_lector_no_devuelve_un_campo_de_inflacion(self):
        """El indice no es la inflacion: convertir es una decision, no una lectura."""
        serie = leer(FUENTE)
        campos = set(serie[0])
        assert "inflacion" not in campos
        assert "inflacion_mensual" not in campos
        assert "valor" in campos


class TestFixtures:
    def test_el_fixture_versionado_lee(self):
        serie = leer(FUENTE)
        assert len(serie) > 0
        assert {f["periodo"] for f in serie}

    def test_la_base_diciembre_2016_vale_100(self):
        """La serie esta en base dic-2016: ese mes es 100.0000 por definicion."""
        serie = leer(FUENTE)
        dic = next(f for f in serie if f["periodo"].startswith("2016-12"))
        assert dic["valor"] == pytest.approx(100.0)

    def test_el_meta_declara_fuente_y_frecuencia(self):
        info = leer(FUENTE, solo_meta=True)
        assert info["frecuencia"] == "month"
        assert "INDEC" in info["fuente"]

    def test_un_fixture_sin_data_se_rechaza(self, tmp_path):
        f = tmp_path / "m.json"
        f.write_text(
            json.dumps({"data": [], "count": 0, "meta": [{"frequency": "month", "start_date": "", "end_date": ""}]}),
            encoding="utf-8",
        )
        with pytest.raises(IpcInvalido, match="sin datos"):
            leer(f, id_serie=ID_NACIONAL_VIVA)

    def test_un_fixture_sin_meta_se_rechaza(self, tmp_path):
        f = tmp_path / "m.json"
        f.write_text(json.dumps({"data": [["2016-12-01", 100.0]], "count": 1}), encoding="utf-8")
        with pytest.raises(IpcInvalido, match="meta"):
            leer(f, id_serie=ID_NACIONAL_VIVA)

    def test_un_fixture_inexistente_se_rechaza(self, tmp_path):
        with pytest.raises(IpcInvalido, match="no está"):
            leer(tmp_path / "no_existe.json")


class TestDescargaNoEsPythonUrllib:
    """La API de datos.gob.ar responde 403 al User-Agent `Python-urllib/*` y 200 a cualquier otro.

    Medido el 09/10/26 con curl (mismo URL: 200 sin -A, 403 con `-A Python-urllib/3.14`).
    `descargar()` nunca habia funcionado desde Python; el fixture del 04/10 se bajo por otro camino.
    """

    def test_el_pedido_declara_un_user_agent_propio(self):
        from uydatos.indec import _pedido

        ua = _pedido().get_header("User-agent") or ""
        assert ua and not ua.lower().startswith("python-urllib")


class TestOtraSerieEnElArchivo:
    def test_un_archivo_de_otra_serie_se_rechaza(self, tmp_path):
        """Pedir la nacional y leer un archivo de GBA daria un indice de otra granularidad."""
        d = json.loads(FUENTE.read_text(encoding="utf-8"))
        d["meta"][1]["field"]["id"] = ID_GBA
        f = tmp_path / "gba.json"
        f.write_text(json.dumps(d), encoding="utf-8")
        with pytest.raises(IpcInvalido, match="GBA|INIVELGBA"):
            leer(f, id_serie=ID_NACIONAL_VIVA)


class TestFactor:
    def test_factor_es_el_cociente_de_indices(self):
        from uydatos.indec import factor

        serie = leer(FUENTE)
        assert factor(serie, "2016-12", "2016-12") == pytest.approx(1.0)
        assert factor(serie, "2017-01", "2016-12") == pytest.approx(1.015859)
        assert factor(serie, "1990-01", "2016-12") is None
