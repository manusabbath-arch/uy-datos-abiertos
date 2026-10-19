"""Tests de `uydatos.revisiones`: comparar dos copias de la misma fuente, sin red."""

from __future__ import annotations

import json

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


def _csv(ruta, filas: list[str], enc: str = "periodo;valor"):
    ruta.write_text(enc + "\n" + "\n".join(filas) + "\n", encoding="utf-8")
    return ruta


def test_revisadas_encuentra_el_pasado_reescrito(tmp_path):
    antes = _csv(tmp_path / "a.csv", ["2026-01;10", "2026-02;20", "2026-03;30"])
    despues = _csv(tmp_path / "b.csv", ["2026-01;10", "2026-02;25", "2026-03;30"])
    r = revisiones.revisadas(antes, despues, clave=["periodo"], valor="valor")
    assert r["revisadas"] == 1
    assert r["mayores"][0]["clave"] == ["2026-02"]
    assert r["mayores"][0]["antes"] == 20.0 and r["mayores"][0]["despues"] == 25.0
    assert r["mayores"][0]["delta"] == 5.0


def test_revisadas_no_cuenta_altas_ni_bajas(tmp_path):
    antes = _csv(tmp_path / "a.csv", ["2026-01;10"])
    despues = _csv(tmp_path / "b.csv", ["2026-01;10", "2026-02;20", "2026-03;30"])
    r = revisiones.revisadas(antes, despues, clave=["periodo"], valor="valor")
    assert r["revisadas"] == 0
    assert r["nuevas"] == 2 and r["borradas"] == 0


def test_revisadas_respeta_la_tolerancia(tmp_path):
    antes = _csv(tmp_path / "a.csv", ["2026-01;10.0"])
    despues = _csv(tmp_path / "b.csv", ["2026-01;10.4"])
    assert revisiones.revisadas(antes, despues, clave=["periodo"], valor="valor")["revisadas"] == 1
    assert revisiones.revisadas(antes, despues, clave=["periodo"], valor="valor", tolerancia=0.5)["revisadas"] == 0


def test_revisadas_rechaza_si_no_esta_la_columna_del_valor(tmp_path):
    antes = _csv(tmp_path / "a.csv", ["2026-01;10"])
    with pytest.raises(RevisionInvalida, match="no hay columna"):
        revisiones.revisadas(antes, antes, clave=["periodo"], valor="monto")


def test_revisadas_cuenta_las_que_no_son_numeros(tmp_path):
    """Un valor no numérico no se puede restar: se cuenta, no se saltea en silencio."""
    antes = _csv(tmp_path / "a.csv", ["2026-01;s/d"])
    despues = _csv(tmp_path / "b.csv", ["2026-01;10"])
    r = revisiones.revisadas(antes, despues, clave=["periodo"], valor="valor")
    assert r["revisadas"] == 0 and r["no_numericas"] == 1


def _fuente(lector, ok=True, filas=100, columnas=("a", "b"), motivo=""):
    return {
        "lector": lector,
        "ok": ok,
        "filas": filas,
        "columnas": list(columnas),
        "bytes": 1,
        "sha256": "x",
        "motivo": motivo,
    }


def _informe(ruta, fuentes: list[dict]):
    ruta.write_text(json.dumps({"fecha": "2026-10-18", "fuentes": fuentes}, ensure_ascii=False), encoding="utf-8")
    return ruta


def test_desde_json_dice_que_se_rompio_y_que_cambio_de_columnas(tmp_path):
    antes = _informe(tmp_path / "fuentes-2026-10-11.json", [_fuente("ancap"), _fuente("inumet")])
    despues = _informe(
        tmp_path / "fuentes-2026-10-18.json",
        [
            _fuente("ancap", ok=False, filas=0, columnas=[], motivo="faltan columnas"),
            _fuente("inumet", columnas=["a", "c"]),
        ],
    )
    r = revisiones.desde_json(antes, despues)
    assert [x["lector"] for x in r["rompieron"]] == ["ancap"]
    assert r["columnas"] == [{"lector": "inumet", "nuevas": ["c"], "idas": ["b"]}]
    assert r["sanos"] == []


def test_desde_json_avisa_una_caida_de_filas_y_lo_que_aparece(tmp_path):
    antes = _informe(tmp_path / "fuentes-2026-10-11.json", [_fuente("inia", filas=1000, columnas=["a"])])
    despues = _informe(
        tmp_path / "fuentes-2026-10-18.json",
        [_fuente("inia", filas=12, columnas=["a"]), _fuente("sanciones", filas=10, columnas=["a"])],
    )
    r = revisiones.desde_json(antes, despues)
    assert r["filas"] == [{"lector": "inia", "antes": 1000, "despues": 12}]
    assert r["aparecen"] == ["sanciones"]


def test_markdown_dice_lo_que_cambio_y_cuenta_las_sanas():
    r = {
        "rompieron": [{"lector": "ancap", "motivo": "DatosInvalidos: faltan columnas"}],
        "columnas": [{"lector": "inumet", "nuevas": ["c"], "idas": ["b"]}],
        "filas": [{"lector": "inia", "antes": 1000, "despues": 12}],
        "aparecen": ["sanciones"],
        "desaparecen": [],
        "sanos": ["bcu"],
    }
    texto = revisiones.markdown(r, titulo="2026-10-19")
    assert texto.startswith("## 2026-10-19")
    assert "| `ancap` | rompió | DatosInvalidos: faltan columnas |" in texto
    assert "| `inumet` | columnas | -b +c |" in texto
    assert "| `inia` | filas | 1000 → 12 |" in texto
    assert "| `sanciones` | aparece |  |" in texto
    assert "sanas 1: bcu" in texto


def test_markdown_sin_cambios_lo_dice():
    """Un informe sin cambios no puede parecer un informe que no se hizo."""
    r = {"rompieron": [], "columnas": [], "filas": [], "aparecen": [], "desaparecen": [], "sanos": ["bcu", "ancap"]}
    texto = revisiones.markdown(r)
    assert "Sin cambios de forma." in texto
    assert "sanas 2: ancap, bcu" in texto
