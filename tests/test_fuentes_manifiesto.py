"""Tests de `uydatos.fuentes`: el manifiesto de las fuentes, sin red."""

from __future__ import annotations

from typing import Optional

import pytest

from uydatos import ancap, catalogo, fuentes
from uydatos.__main__ import LECTORES

SIN_FUENTE = {"red"}  # `red` no lee una fuente: es la única salida a internet del paquete.


def test_el_manifiesto_cubre_a_todos_los_lectores():
    """Agregar un lector a `LECTORES` sin su fila en el manifiesto se cae acá."""
    esperados = (set(LECTORES) - SIN_FUENTE) | {"rut", "semanas"}
    faltan = sorted(esperados - set(fuentes.FUENTES))
    sobran = sorted(set(fuentes.FUENTES) - esperados)
    assert not faltan, f"lectores sin fila en el manifiesto: {faltan}"
    assert not sobran, f"filas sin lector: {sobran}"


def _recursos(modificado: str, url: Optional[str] = None) -> list[dict]:
    # El nombre del archivo no es un dato del test: es el que declara ANCAP. Con un nombre
    # inventado, `deriva` no encuentra candidato y el test mide otra cosa.
    return [
        {
            "nombre": "precios",
            "url": url or f"https://x/{ancap.NOMBRE_CSV}",
            "formato": "CSV",
            "modificado": modificado,
        }
    ]


def test_deriva_avisa_cuando_el_recurso_se_modifico(monkeypatch):
    monkeypatch.setattr(catalogo, "recursos", lambda dataset: _recursos("2026-11-01T10:00:00"))
    r = fuentes.deriva("ancap")
    assert r["movido"] is True
    assert r["detalle"][0]["modificado"] == "2026-11-01"


def test_deriva_no_avisa_cuando_el_recurso_es_el_medido(monkeypatch):
    monkeypatch.setattr(catalogo, "recursos", lambda dataset: _recursos("2026-10-12T09:00:00"))
    assert fuentes.deriva("ancap")["movido"] is False


def test_deriva_rechaza_si_hay_dos_archivos_candidatos(monkeypatch):
    dos = _recursos("2026-10-12") + _recursos("2026-10-13", f"https://x/vieja/{ancap.NOMBRE_CSV}")
    monkeypatch.setattr(catalogo, "recursos", lambda dataset: dos)
    with pytest.raises(catalogo.CatalogoInvalido, match="se esperaba 1"):
        fuentes.deriva("ancap")


def test_deriva_dice_que_una_fuente_sin_catalogo_se_mide_a_mano():
    r = fuentes.deriva("rut")
    assert r["movido"] is False
    assert "a mano" in r["motivo"]


def test_deriva_rechaza_un_lector_que_no_esta():
    with pytest.raises(KeyError, match="no está en el manifiesto"):
        fuentes.deriva("no-existe")


@pytest.mark.red
def test_cada_fuente_del_manifiesto_resuelve_a_un_recurso():
    """El manifiesto contra el catálogo real: cada dataset existe y cada lector con nombre de
    archivo encuentra exactamente uno. Medido el 2026-10-17."""
    for nombre, f in sorted(fuentes.FUENTES.items()):
        if not f["datasets"]:
            continue
        r = fuentes.deriva(nombre)
        assert len(r["detalle"]) == len(f["datasets"]), (nombre, r)
