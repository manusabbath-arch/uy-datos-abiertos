"""Tests del lector del IPCA (IBGE, API SIDRA, tabla 1737, variable 2266).

- **`TestVariable`**: la tabla 1737 trae varias variables (variacion mensual, acumulada en 12 meses,
  numero-indice). Leer la variacion como indice da una serie que "funciona" y miente. El lector
  exige la variable 2266 y la unidad `Número-índice`.
- **`TestSinDato`**: SIDRA marca el dato faltante con `...` o `-`: es un nulo, no un cero.
- **`TestEncabezado`**: la primera fila de la respuesta es el diccionario de columnas, no un dato.
- **`TestPedido`**: la descarga declara un User-Agent propio (la API argentina rechaza el de Python;
  no se espera a que esta haga lo mismo).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from uydatos.ibge import IpcaInvalido, _pedido, leer

_ENC = {
    "NC": "Nível Territorial (Código)",
    "MN": "Unidade de Medida",
    "V": "Valor",
    "D2C": "Variável (Código)",
    "D3C": "Mês (Código)",
}


def _fila(periodo: str, valor: str, var: str = "2266", unidad: str = "Número-índice") -> dict:
    return {"NC": "1", "MN": unidad, "V": valor, "D2C": var, "D3C": periodo}


def _archivo(tmp_path: Path, filas: list[dict]) -> Path:
    p = tmp_path / "ipca.json"
    p.write_text(json.dumps([_ENC, *filas], ensure_ascii=False), encoding="utf-8")
    return p


class TestVariable:
    def test_lee_el_indice(self, tmp_path):
        p = _archivo(tmp_path, [_fila("202201", "6153.09"), _fila("202202", "6215.02")])
        assert leer(p) == [{"periodo": "2022-01", "valor": 6153.09}, {"periodo": "2022-02", "valor": 6215.02}]

    def test_otra_variable_se_rechaza(self, tmp_path):
        p = _archivo(tmp_path, [_fila("202201", "0.54", var="63", unidad="%")])
        with pytest.raises(IpcaInvalido, match="2266"):
            leer(p)


class TestSinDato:
    def test_puntos_suspensivos_es_nulo_no_cero(self, tmp_path):
        p = _archivo(tmp_path, [_fila("202201", "6153.09"), _fila("202202", "...")])
        assert leer(p) == [{"periodo": "2022-01", "valor": 6153.09}]


class TestEncabezado:
    def test_respuesta_sin_datos_se_rechaza(self, tmp_path):
        with pytest.raises(IpcaInvalido):
            leer(_archivo(tmp_path, []))

    def test_el_recorte_real_se_lee(self):
        """Recorte de la respuesta real de SIDRA: base dic-1993 = 100."""
        serie = leer(Path(__file__).parent / "fixtures" / "ibge_ipca_recorte.json")
        assert next(s["valor"] for s in serie if s["periodo"] == "1993-12") == 100
        assert all(s["valor"] > 6000 for s in serie if s["periodo"] >= "2022-01")


class TestPedido:
    def test_user_agent_propio(self):
        ua = _pedido().get_header("User-agent") or ""
        assert ua and not ua.lower().startswith("python-urllib")
