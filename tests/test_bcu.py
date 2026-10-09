"""Tests del lector de cotizaciones del BCU (`uydatos.bcu`).

Fijan las trampas que el docstring de `uydatos.bcu` declara:

- **`TestRespuestaMala`**: una respuesta con `status 0` o `codigoerror` distinto de 0 **igual
  se guarda** en `crudo/`. El lector la rechaza en vez de devolver una serie vacia que se lea
  como "no hubo cotizacion".
- **`TestUnaMonedaPorArchivo`**: un crudo que mezcla dos monedas, o que no es la moneda que
  se pidio, se rechaza. La UI (9800) leida como dolar daria un IVA absurdo sin error.
- **`TestDiaSinPublicacion`**: fines de semana y feriados no vienen. Que cotizacion le toca a
  un dia sin publicacion es una **decision explicita** (`hacia_atras=True`, el ultimo dia
  habil previo), nunca un hueco que se rellena en silencio.
- **`TestPromedioMensual`**: el promedio del mes declara cuantos dias lo forman; el mes en
  curso viene parcial y no puede pasar por un mes completo.
- **`TestFixtures`**: los tests leen archivos de `tmp_path`, no la red.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from uydatos.bcu import (
    MONEDAS,
    BcuInvalido,
    a_pesos_de,
    cotizacion_del_dia,
    leer_crudo,
    leer_serie,
    promedio_mensual,
)


def _xml(datos: list[tuple[str, int, float]], status: int = 1, codigo: int = 0) -> str:
    filas = "".join(
        f'<datoscotizaciones.dato xmlns="Cotiza"><Fecha>{f}</Fecha><Moneda>{m}</Moneda>'
        f"<Nombre>X</Nombre><CodigoISO>X</CodigoISO><Emisor>X</Emisor>"
        f"<TCC>{v:.6f}</TCC><TCV>{v:.6f}</TCV><ArbAct>1</ArbAct><FormaArbitrar>0</FormaArbitrar>"
        f"</datoscotizaciones.dato>"
        for f, m, v in datos
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"><SOAP-ENV:Body>'
        '<wsbcucotizaciones.ExecuteResponse xmlns="Cotiza"><Salida xmlns="Cotiza">'
        f"<respuestastatus><status>{status}</status><codigoerror>{codigo}</codigoerror><mensaje/></respuestastatus>"
        f"<datoscotizaciones>{filas}</datoscotizaciones>"
        "</Salida></wsbcucotizaciones.ExecuteResponse></SOAP-ENV:Body></SOAP-ENV:Envelope>"
    )


def _archivo(tmp_path: Path, nombre: str, contenido: str) -> Path:
    p = tmp_path / nombre
    p.write_text(contenido, encoding="utf-8")
    return p


class TestRespuestaMala:
    def test_status_cero_se_rechaza(self, tmp_path):
        p = _archivo(tmp_path, "2225_2026-01.xml", _xml([], status=0, codigo=104))
        with pytest.raises(BcuInvalido, match="104"):
            leer_crudo(p, moneda=2225)

    def test_respuesta_buena_sin_datos_se_rechaza(self, tmp_path):
        """Un mes sin un solo dia no es un mes sin cotizacion: es una respuesta inservible."""
        p = _archivo(tmp_path, "2225_2026-01.xml", _xml([]))
        with pytest.raises(BcuInvalido, match="sin datos"):
            leer_crudo(p, moneda=2225)


class TestUnaMonedaPorArchivo:
    def test_otra_moneda_se_rechaza(self, tmp_path):
        p = _archivo(tmp_path, "2225_2026-01.xml", _xml([("2026-01-02", 9800, 6.3)]))
        with pytest.raises(BcuInvalido, match="9800"):
            leer_crudo(p, moneda=2225)

    def test_dos_monedas_en_un_archivo_se_rechaza(self, tmp_path):
        p = _archivo(tmp_path, "501_2026-01.xml", _xml([("2026-01-02", 501, 0.03), ("2026-01-02", 500, 0.03)]))
        with pytest.raises(BcuInvalido):
            leer_crudo(p, moneda=501)

    def test_dia_repetido_se_rechaza(self, tmp_path):
        p = _archivo(tmp_path, "501_2026-01.xml", _xml([("2026-01-02", 501, 0.03), ("2026-01-02", 501, 0.04)]))
        with pytest.raises(BcuInvalido, match="repetid"):
            leer_crudo(p, moneda=501)

    def test_las_monedas_declaradas(self):
        assert MONEDAS[2225].startswith("DLS")
        assert "INDEXADA" in MONEDAS[9800]
        assert "ARG" in MONEDAS[501]
        assert MONEDAS[1001] == "REAL BILLETE"


class TestDiaSinPublicacion:
    def _serie(self, tmp_path):
        p = _archivo(
            tmp_path,
            "2225_2026-01.xml",
            _xml([("2026-01-02", 2225, 40.0), ("2026-01-05", 2225, 41.0)]),
        )
        return leer_crudo(p, moneda=2225)

    def test_dia_publicado(self, tmp_path):
        assert cotizacion_del_dia(self._serie(tmp_path), date(2026, 1, 5)) == 41.0

    def test_sabado_sin_decision_es_none(self, tmp_path):
        assert cotizacion_del_dia(self._serie(tmp_path), date(2026, 1, 3)) is None

    def test_sabado_hacia_atras_toma_el_viernes(self, tmp_path):
        assert cotizacion_del_dia(self._serie(tmp_path), date(2026, 1, 3), hacia_atras=True) == 40.0

    def test_antes_del_primer_dato_es_none_aun_hacia_atras(self, tmp_path):
        assert cotizacion_del_dia(self._serie(tmp_path), date(2026, 1, 1), hacia_atras=True) is None

    def test_hacia_atras_no_salta_mas_de_una_semana(self, tmp_path):
        """Un hueco de un mes no es un fin de semana: rellenarlo esconde un crudo que falta."""
        assert cotizacion_del_dia(self._serie(tmp_path), date(2026, 2, 20), hacia_atras=True) is None


class TestPromedioMensual:
    def test_promedio_declara_los_dias(self, tmp_path):
        p = _archivo(
            tmp_path,
            "2225_2026-01.xml",
            _xml([("2026-01-02", 2225, 40.0), ("2026-01-05", 2225, 42.0)]),
        )
        meses = promedio_mensual(leer_crudo(p, moneda=2225))
        assert meses == [{"mes": "2026-01", "promedio": 41.0, "dias": 2}]


class TestFixtures:
    def test_leer_serie_no_mezcla_monedas_por_nombre_de_archivo(self, tmp_path):
        _archivo(tmp_path, "2225_2026-01.xml", _xml([("2026-01-02", 2225, 40.0)]))
        _archivo(tmp_path, "9800_2026-01.xml", _xml([("2026-01-02", 9800, 6.3)]))
        assert leer_serie(tmp_path, moneda=9800) == {date(2026, 1, 2): 6.3}


class TestPesosConstantes:
    def test_lleva_cada_mes_a_los_pesos_del_mes_base(self):
        ui = {"2025-01": 6.0, "2026-01": 6.3}
        assert a_pesos_de({"2025-01": 100.0, "2026-01": 100.0}, "2026-01", ui=ui) == {
            "2025-01": pytest.approx(105.0),
            "2026-01": pytest.approx(100.0),
        }

    def test_mes_sin_ui_se_rechaza_en_vez_de_quedar_nominal(self):
        with pytest.raises(BcuInvalido, match="2021-12"):
            a_pesos_de({"2021-12": 100.0}, "2026-01", ui={"2026-01": 6.3})
