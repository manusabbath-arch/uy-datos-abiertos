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


@pytest.mark.red
def test_el_archivo_real_del_dss(tmp_path):
    """El archivo real, con lo medido el 2026-10-17: 168.759 bytes, sha256 241a78a1…, 1.528 filas,
    483 por «Precio no informado» y **0 en Salto**. Si esto cambia, la fuente se movió: se vuelve
    a medir y se actualiza el docstring, no el test."""
    from uydatos.procedencia import sha256

    destino = sanciones.descargar(tmp_path / "datos_sanciones.csv")
    assert sha256(destino) == "241a78a15e951bf960f93efc12aebe0d04dc343b24198a2fa4899d1872dd4cd0"
    filas = sanciones.leer(destino)
    r = sanciones.resumen(filas)
    assert r["filas"] == 1528
    assert r["por_motivo"]["Precio no informado"] == 483
    assert r["por_tipo"] == {"Apercibimiento": 831, "Multa": 695, "Instrucción": 2}
    assert r["rut_sin_12"] == 1
    assert "SALTO" not in r["departamentos"], "hay resoluciones en Salto: actualizar el docstring"
