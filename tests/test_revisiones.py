"""Tests de `uydatos.revisiones`: comparar dos copias de la misma fuente, sin red."""

from __future__ import annotations

import pytest

from uydatos import revisiones
from uydatos.revisiones import RevisionInvalida, comparar

ENCABEZADO = "producto;anio;mes;precio\n"


def _escribir(p, filas: list[str]):
    p.write_text(ENCABEZADO + "\n".join(filas) + "\n", encoding="utf-8")
    return p


def test_dos_archivos_iguales_no_reportan_cambio(tmp_path):
    a = _escribir(tmp_path / "a.csv", ["gasoil;2026;8;62,50", "super;2026;8;80,10"])
    b = _escribir(tmp_path / "b.csv", ["gasoil;2026;8;62,50", "super;2026;8;80,10"])
    r = revisiones.comparar(a, b, clave=("producto", "anio", "mes"))
    assert r["cambio"] is False
    assert (r["filas_agregadas"], r["filas_quitadas"], r["filas_cambiadas"]) == (0, 0, 0)


def test_una_fila_nueva_se_cuenta(tmp_path):
    a = _escribir(tmp_path / "a.csv", ["gasoil;2026;8;62,50"])
    b = _escribir(tmp_path / "b.csv", ["gasoil;2026;8;62,50", "gasoil;2026;9;63,00"])
    r = comparar(a, b, clave=("producto", "anio", "mes"))
    assert r["filas_agregadas"] == 1
    assert r["claves_agregadas"] == [["gasoil", "2026", "9"]]


def test_una_fila_que_falta_se_cuenta(tmp_path):
    a = _escribir(tmp_path / "a.csv", ["gasoil;2026;8;62,50", "super;2026;8;80,10"])
    b = _escribir(tmp_path / "b.csv", ["gasoil;2026;8;62,50"])
    r = comparar(a, b, clave=("producto", "anio", "mes"))
    assert (r["filas_quitadas"], r["claves_quitadas"]) == (1, [["super", "2026", "8"]])


def test_un_precio_revisado_se_cuenta_con_su_clave(tmp_path):
    a = _escribir(tmp_path / "a.csv", ["gasoil;2026;8;62,50"])
    b = _escribir(tmp_path / "b.csv", ["gasoil;2026;8;62,90"])
    r = comparar(a, b, clave=("producto", "anio", "mes"))
    assert r["cambio"] is True
    assert (r["filas_cambiadas"], r["claves_cambiadas"]) == (1, [["gasoil", "2026", "8"]])
    assert r["filas_agregadas"] == r["filas_quitadas"] == 0


def test_un_encabezado_distinto_se_rechaza(tmp_path):
    a = _escribir(tmp_path / "a.csv", ["gasoil;2026;8;62,50"])
    b = tmp_path / "b.csv"
    b.write_text("producto;anio;mes;precio;unidad\ngasoil;2026;8;62,50;$/lt\n", encoding="utf-8")
    with pytest.raises(RevisionInvalida, match=r"agregadas \['unidad'\].*otra fuente"):
        comparar(a, b, clave=("producto", "anio", "mes"))
    # las mismas columnas en otro orden también son otra fuente, y el motivo tiene que decirlo
    c = tmp_path / "c.csv"
    c.write_text("anio;producto;mes;precio\n2026;gasoil;8;62,50\n", encoding="utf-8")
    with pytest.raises(RevisionInvalida, match=r"otro orden.*otra fuente"):
        comparar(a, c, clave=("producto", "anio", "mes"))


def test_una_clave_repetida_se_rechaza_con_el_motivo(tmp_path):
    a = _escribir(tmp_path / "a.csv", ["gasoil;2026;8;62,50", "gasoil;2026;8;62,90"])
    b = _escribir(tmp_path / "b.csv", ["gasoil;2026;8;62,50"])
    with pytest.raises(RevisionInvalida, match=r"a\.csv\)? fila 3: clave repetida \('gasoil', '2026', '8'\)"):
        comparar(a, b, clave=("producto", "anio", "mes"))


def test_una_fila_sin_clave_se_cuenta_en_las_dos_copias_y_no_rompe(tmp_path):
    a = _escribir(tmp_path / "a.csv", ["gasoil;2026;8;62,50", ";2026;8;1,00"])
    b = _escribir(tmp_path / "b.csv", ["gasoil;2026;8;62,50", ";2026;9;2,00"])
    r = comparar(a, b, clave=("producto", "anio", "mes"))
    assert r["sin_clave"] == 2
    assert r["cambio"] is False


def test_una_codificacion_equivocada_se_rechaza_con_el_archivo(tmp_path):
    a = _escribir(tmp_path / "a.csv", ["gasoil;2026;8;62,50"])
    b = tmp_path / "b.csv"
    b.write_bytes("producto;anio;mes;precio\nPérez;2026;8;1,00\n".encode("cp1252"))
    with pytest.raises(RevisionInvalida, match=r"b\.csv: no se puede leer como utf-8"):
        comparar(a, b, clave=("producto", "anio", "mes"))
    r = comparar(a, b, clave=("producto", "anio", "mes"), codificacion="cp1252")
    assert r["claves_agregadas"] == [["Pérez", "2026", "8"]]
