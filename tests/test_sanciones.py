"""Tests del lector de sanciones de Defensa del Consumidor, sin red."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from uydatos import catalogo, sanciones
from uydatos.sanciones import SancionesInvalido


def test_url_vigente_elige_el_unico_csv(monkeypatch):
    monkeypatch.setattr(
        catalogo,
        "recursos",
        lambda dataset: [
            {
                "nombre": "Metadatos de sanciones aplicadas a empresas",
                "url": "https://x/meta.txt",
                "formato": "TXT",
                "modificado": "2025-05-26",
            },
            {
                "nombre": "Sanciones aplicadas a empresas",
                "url": "https://x/datos.csv",
                "formato": "CSV",
                "modificado": "2026-03-22",
            },
        ],
    )
    assert sanciones.url_vigente() == "https://x/datos.csv"


def test_url_vigente_rechaza_si_hay_dos_csv(monkeypatch):
    monkeypatch.setattr(
        catalogo,
        "recursos",
        lambda dataset: [
            {"nombre": "uno", "url": "https://x/1.csv", "formato": "CSV", "modificado": ""},
            {"nombre": "dos", "url": "https://x/2.csv", "formato": "CSV", "modificado": ""},
        ],
    )
    with pytest.raises(SancionesInvalido, match="se esperaba 1"):
        sanciones.url_vigente()


ENCABEZADO = "razon_social;nombre_comercial;rut;departamento;fecha_resolucion;motivo_sancion;tipo_sancion;monto_ur"

FILAS = [
    "A PURA MANO LTDA;NUEVA ESTAMPA;219000000004    ;MONTEVIDEO;31/5/2018;Precio no informado;Apercibimiento;0",
    "PANADERIA ÑANDU;LA ÑANDU;210000000018;SALTO;20/7/2018;Publicidad engañosa;Multa;120",
    "OTRA SA;;123;CANELONES;21/10/2024;Incomparecencia;Multa;30",
]


def _escribir(p: Path) -> Path:
    p.write_text("\n".join([ENCABEZADO, *FILAS]) + "\n", encoding="cp1252")
    return p


def test_lee_las_filas_tal_cual(tmp_path):
    filas = sanciones.leer(_escribir(tmp_path / "s.csv"))
    assert len(filas) == 3
    assert filas[0]["razon_social"] == "A PURA MANO LTDA"
    assert filas[1]["razon_social"] == "PANADERIA ÑANDU"  # cp1252, no UTF-8
    assert filas[0]["fecha"] == date(2018, 5, 31)


def test_el_rut_viene_con_relleno_y_se_limpia(tmp_path):
    filas = sanciones.leer(_escribir(tmp_path / "s.csv"))
    assert filas[0]["rut"] == "219000000004"


def test_un_rut_de_tres_caracteres_no_se_descarta(tmp_path):
    filas = sanciones.leer(_escribir(tmp_path / "s.csv"))
    assert filas[2]["rut"] == "123"
    assert sanciones.resumen(filas)["rut_sin_12"] == 1


def test_una_fecha_de_ancho_variable_se_lee(tmp_path):
    filas = sanciones.leer(_escribir(tmp_path / "s.csv"))
    assert [f["fecha"] for f in filas] == [date(2018, 5, 31), date(2018, 7, 20), date(2024, 10, 21)]


def test_un_monto_cero_es_cero_y_no_nulo(tmp_path):
    filas = sanciones.leer(_escribir(tmp_path / "s.csv"))
    assert filas[0]["monto_ur"] == 0
    assert filas[0]["monto_ur"] is not None


def test_una_columna_de_mas_se_rechaza(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text(ENCABEZADO + ";extra\n" + FILAS[0] + ";x\n", encoding="cp1252")
    with pytest.raises(SancionesInvalido, match="columnas"):
        sanciones.leer(p)


def test_una_fecha_ilegible_se_rechaza(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text("\n".join([ENCABEZADO, FILAS[0].replace("31/5/2018", "2018-05-31")]) + "\n", encoding="cp1252")
    with pytest.raises(SancionesInvalido, match="fecha"):
        sanciones.leer(p)


# La forma del archivo publicado el 2026-11-03 (`datos_sanciones_2017_2025.csv`), medido el
# 2026-11-06: la sexta columna se llama `tipo_infraccion` y el RUT pasó por una planilla. Empresas y
# RUT inventados (el repositorio no publica los de terceros: ver `test_privacidad.py`); las formas
# —el RUT truncado compartido, el `N/D`, la fila de 2025 sin departamento ni monto— son las medidas.
ENCABEZADO_2025 = ENCABEZADO.replace("motivo_sancion", "tipo_infraccion")
FILAS_2025 = [
    "EMPRESA UNO LTDA;LA UNO;2,17795E+11;MONTEVIDEO;31/5/2018;Precio no informado;Apercibimiento;0",
    "EMPRESA DOS S.A.;LA DOS;2,17795E+11;MONTEVIDEO;26/11/2024;Practica abusiva;Multa;100",
    "EMPRESA TRES SRL;LA TRES;219000000004;CANELONES;5/5/2020;Información no clara;Apercibimiento;0",
    "EMPRESA CUATRO;EMPRESA CUATRO;N/D;CANELONES;16/5/2024;Incomparecencia;Multa;10",
    "EMPRESA CINCO SA;;2,13661E+11;;29/1/2025;Garantía falta información;Apercibimiento;",
    "EMPRESA SEIS S.R.L;LA SEIS;2,17562E+11;;31/1/2025;Información no veraz;Instrucción;",
]


def _escribir_2025(p: Path) -> Path:
    p.write_text("\r\n".join([ENCABEZADO_2025, *FILAS_2025]) + "\r\n", encoding="cp1252")
    return p


def test_el_encabezado_de_2025_se_acepta_y_el_motivo_llega_igual(tmp_path):
    filas = sanciones.leer(_escribir_2025(tmp_path / "s.csv"))
    assert len(filas) == 6
    assert filas[0]["motivo"] == "Precio no informado"
    assert filas[5]["tipo"] == "Instrucción"


def test_el_rut_en_notacion_cientifica_es_nulo_y_nunca_un_numero(tmp_path):
    filas = sanciones.leer(_escribir_2025(tmp_path / "s.csv"))
    assert filas[0]["rut"] is None and filas[0]["rut_crudo"] == "2,17795E+11"
    assert filas[0]["rut_en_notacion_cientifica"]
    assert filas[2]["rut"] == "219000000004" and not filas[2]["rut_en_notacion_cientifica"]
    assert filas[3]["rut"] is None and not filas[3]["rut_en_notacion_cientifica"]  # N/D


def test_dos_empresas_con_el_mismo_rut_truncado_se_cuentan(tmp_path):
    # Dos empresas distintas con el mismo RUT truncado: agrupar por RUT las junta (medido: 120 RUT así)
    r = sanciones.resumen(sanciones.leer(_escribir_2025(tmp_path / "s.csv")))
    assert r["rut_en_notacion_cientifica"] == 4
    assert r["rut_truncado_compartido"] == 1 and r["filas_con_rut_compartido"] == 2
    assert r["rut_nulo"] == 5


def test_en_2025_el_monto_y_el_departamento_vacios_son_nulos(tmp_path):
    filas = sanciones.leer(_escribir_2025(tmp_path / "s.csv"))
    assert filas[4]["monto_ur"] is None and filas[4]["departamento"] is None
    assert filas[0]["monto_ur"] == 0  # el cero de un apercibimiento de 2018 sigue siendo un cero
    r = sanciones.resumen(filas)
    assert (r["monto_nulo"], r["sin_departamento"]) == (2, 2)


@pytest.mark.parametrize(
    "crudo, esperado",
    [
        ("219000000004    ", ("219000000004", False)),
        ("2,17795E+11", (None, True)),
        ("2,1885E+11", (None, True)),
        ("N/D", (None, False)),
        ("", (None, False)),
        ("123", ("123", False)),
    ],
)
def test_rut(crudo, esperado):
    assert sanciones.rut(crudo) == esperado


@pytest.mark.red
def test_el_archivo_real_del_dss(tmp_path):
    """El archivo real, con lo medido el 2026-11-06 (publicado el 2026-11-03): 191.915 bytes,
    sha256 23894813…, 1.835 filas, 607 por «Precio no informado», **0 en Salto**, y el RUT en
    notación científica en 1.738. Antes (2026-10-17) eran 168.759 bytes y 1.528 filas. Si esto
    cambia, la fuente se movió: se vuelve a medir y se actualiza el docstring, no el test."""
    from uydatos.procedencia import sha256

    destino = sanciones.descargar(tmp_path / "datos_sanciones.csv")
    assert sha256(destino) == "2389481356510dbfa2115bf33312e286349eeae4527500fdcc2e25b6a066eb26"
    filas = sanciones.leer(destino)
    r = sanciones.resumen(filas)
    assert r["filas"] == 1835
    assert r["por_motivo"]["Precio no informado"] == 607
    assert r["por_tipo"] == {"Apercibimiento": 1060, "Multa": 772, "Instrucción": 3}
    assert r["rut_sin_12"] == 1
    assert r["rut_en_notacion_cientifica"] == 1738 and r["rut_truncado_compartido"] == 120
    assert (r["monto_nulo"], r["sin_departamento"]) == (230, 307)
    assert "SALTO" not in r["departamentos"], "hay resoluciones en Salto: actualizar el docstring"
