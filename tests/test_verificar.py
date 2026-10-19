"""El contrato de forma de las fuentes: filas, columnas, bytes y sha256. Sin red salvo el marcado."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from uydatos import errores, fuentes, verificar

CONTENIDO = "a;b\n1;2\n"


def _escritor(columnas, filas, falla=None, directorio=False):
    # `newline="\n"`: en Windows `write_text` traduce el salto a CRLF y el archivo mide 10 bytes
    # donde el test pide 8. El sello se mide sobre los bytes que hay en disco, así que la fixture
    # tiene que dejar los mismos bytes en cualquier sistema.
    def escribir(d: Path) -> dict:
        if falla:
            raise falla
        if directorio:
            (d / "sub").mkdir()
            (d / "sub" / "uno.csv").write_text(CONTENIDO, encoding="utf-8", newline="\n")
            (d / "dos.csv").write_text(CONTENIDO, encoding="utf-8", newline="\n")
            return {"ruta": d, "filas": filas, "columnas": columnas}
        ruta = d / "x.csv"
        ruta.write_text(CONTENIDO, encoding="utf-8", newline="\n")
        return {"ruta": ruta, "filas": filas, "columnas": columnas}

    return escribir


def test_verificar_devuelve_la_forma_y_el_sello(monkeypatch, tmp_path):
    monkeypatch.setitem(verificar.VERIFICAR, "ancap", _escritor(["a", "b"], 12))
    r = verificar.verificar("ancap", tmp_path)
    assert r["ok"] is True
    assert r["filas"] == 12 and r["columnas"] == ["a", "b"]
    assert r["bytes"] == len(CONTENIDO.encode("utf-8"))
    assert r["sha256"] == hashlib.sha256(CONTENIDO.encode("utf-8")).hexdigest()


def test_verificar_sella_un_conjunto_de_archivos(monkeypatch, tmp_path):
    """INIA son 57 CSV en un directorio: el sello tiene que ser del conjunto, no del último archivo."""
    monkeypatch.setitem(verificar.VERIFICAR, "inia", _escritor(["a"], 5, directorio=True))
    r1 = verificar.verificar("inia", tmp_path / "a")
    r2 = verificar.verificar("inia", tmp_path / "b")
    assert r1["ok"] is True and r1["bytes"] == 2 * len(CONTENIDO)
    assert r1["sha256"] == r2["sha256"], "el mismo conjunto tiene que dar el mismo sha256"


def test_verificar_dice_que_falta_un_parametro():
    r = verificar.verificar("ideuy")
    assert r["ok"] is False
    assert r["motivo"].startswith("requiere") and "dirección" in r["motivo"]


def test_verificar_atrapa_el_rechazo_del_lector(monkeypatch, tmp_path):
    monkeypatch.setitem(verificar.VERIFICAR, "ancap", _escritor([], 0, errores.DatosInvalidos("faltan columnas")))
    r = verificar.verificar("ancap", tmp_path)
    assert r["ok"] is False
    assert "faltan columnas" in r["motivo"]


def test_verificar_no_deja_pasar_una_fuente_vacia(monkeypatch, tmp_path):
    monkeypatch.setitem(verificar.VERIFICAR, "ancap", _escritor(["a"], 0))
    assert verificar.verificar("ancap", tmp_path)["ok"] is False


def test_los_adaptadores_y_las_pendientes_parten_el_manifiesto():
    """Igual que el manifiesto con `LECTORES`: una fuente nueva sin adaptador ni motivo se cae acá."""
    assert set(verificar.VERIFICAR) | set(verificar.PENDIENTES) == set(fuentes.FUENTES)
    assert not set(verificar.VERIFICAR) & set(verificar.PENDIENTES)


def test_el_informe_json_es_comparable(monkeypatch, tmp_path):
    monkeypatch.setitem(verificar.VERIFICAR, "ancap", _escritor(["a"], 3))
    monkeypatch.setitem(verificar.VERIFICAR, "sanciones", _escritor(["a"], 4))
    destino = tmp_path / "fuentes-2026-10-18.json"
    assert verificar.main(["--json", str(destino), "sanciones", "ancap"]) == 0
    datos = json.loads(destino.read_text(encoding="utf-8"))
    assert datos["fecha"]
    assert [f["lector"] for f in datos["fuentes"]] == ["ancap", "sanciones"], "el informe va ordenado"
    assert {f["ok"] for f in datos["fuentes"]} == {True}


@pytest.mark.red
def test_dos_fuentes_reales_se_verifican():
    """Contra el catálogo de verdad. Medido el 2026-10-19: ANCAP 893.940 bytes, sanciones 168.759."""
    for lector in ("ancap", "sanciones"):
        r = verificar.verificar(lector)
        assert r["ok"] is True, (lector, r["motivo"])
        assert r["filas"] > 100
        assert r["sha256"]
