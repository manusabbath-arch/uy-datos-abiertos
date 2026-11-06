"""Lo común a los tests: dónde están los recortes reales y cómo se modifica uno sin tocarlo."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def recorte():
    """La ruta de un recorte real, medido el 2026-11-06."""
    return lambda nombre: FIXTURES / nombre


@pytest.fixture
def modificado(tmp_path):
    """Copia un recorte JSON a `tmp_path` después de pasarlo por `cambio(d)`: así cada test de
    rechazo parte de la respuesta real y cambia **una** cosa."""

    def _hacer(nombre: str, cambio) -> Path:
        d = json.loads((FIXTURES / nombre).read_text(encoding="utf-8"))
        cambio(d)
        p = tmp_path / nombre
        p.write_text(json.dumps(d), encoding="utf-8")
        return p

    return _hacer
