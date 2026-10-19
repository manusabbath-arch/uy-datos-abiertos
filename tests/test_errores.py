"""El contrato de errores: una sola base para los rechazos de las 21 fuentes."""

from __future__ import annotations

import importlib
import inspect
import pkgutil

import pytest

import uydatos
from uydatos import ancap, errores


def _modulos():
    for info in pkgutil.iter_modules(uydatos.__path__):
        yield importlib.import_module(f"uydatos.{info.name}")


def _clases_de_rechazo():
    """Toda clase del paquete que se llame `*Invalido`/`*Invalida` y sea un `ValueError`.

    Se descubre por introspección a propósito: un lector nuevo con su `*Invalido` suelto cae acá sin
    que nadie se acuerde de agregarlo a una lista.
    """
    for modulo in _modulos():
        for nombre, clase in inspect.getmembers(modulo, inspect.isclass):
            if (
                clase.__module__ == modulo.__name__
                and nombre.endswith(("Invalido", "Invalida"))
                and issubclass(clase, ValueError)
            ):
                yield clase


def test_el_paquete_tiene_las_clases_de_rechazo_que_se_esperan():
    clases = list(_clases_de_rechazo())
    assert len(clases) >= 19, f"solo {len(clases)}: el contrato cambió y este test no se enteró"


def test_todas_las_clases_de_rechazo_heredan_de_datos_invalidos():
    sueltas = sorted(c.__name__ for c in _clases_de_rechazo() if not issubclass(c, errores.DatosInvalidos))
    assert not sueltas, f"no heredan de DatosInvalidos: {sueltas}"


def test_una_sola_base_atrapa_el_rechazo_de_cualquier_lector(tmp_path):
    """Lo que el consumidor necesita: un `except` y no diecinueve. El mensaje sigue siendo del
    dominio (lo dice `AncapInvalido`), pero el tipo que se atrapa es uno."""
    ruta = tmp_path / "mala.csv"
    ruta.write_text("otra;cosa\n1;2\n", encoding="utf-8")
    with pytest.raises(errores.DatosInvalidos):
        ancap.leer_publicaciones(ruta)
