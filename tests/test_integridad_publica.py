import pytest

from uydatos.integridad_publica import resumir


def fila(nombre, ok=True, sha="a" * 64):
    return {"lector": nombre, "ok": ok, "sha256": sha, "bytes": 8, "motivo": "dato privado no debe salir"}


def test_sello_compartido_no_es_falla_de_fuente():
    r = resumir({"fecha": "2026-10-19", "fuentes": [fila("bcu"), fila("inia"), fila("otro", False)]})
    assert r["lectura_ok"] == 2
    assert r["sin_verificacion_ok"] == 1
    assert r["alertas"][0]["lectores"] == ["bcu", "inia"]
    assert "dato privado" not in str(r)


def test_sellos_distintos():
    assert not resumir({"fecha": "2026-10-19", "fuentes": [fila("a"), fila("b", sha="b" * 64)]})["alertas"]


def test_duplicado_rechazado():
    with pytest.raises(ValueError):
        resumir({"fecha": "2026-10-19", "fuentes": [fila("a"), fila("a")]})


def test_hash_invalido():
    with pytest.raises(ValueError):
        resumir({"fecha": "2026-10-19", "fuentes": [fila("a", sha="mal")]})
