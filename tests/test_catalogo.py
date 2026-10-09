"""Tests de `uydatos.catalogo`: la respuesta de `package_show` de CKAN, sin red."""

from __future__ import annotations

import pytest

from uydatos.catalogo import CatalogoInvalido, parsear_package_show


def _respuesta(recursos, success=True):
    return {"success": success, "result": {"resources": recursos}}


def test_lista_los_recursos():
    r = parsear_package_show(
        _respuesta(
            [
                {
                    "name": "ppt_tmax_tmin_sg_2026",
                    "url": "https://catalogodatos.gub.uy/x/ppt_tmax_tmin_sg_2026.csv",
                    "format": "csv",
                    "last_modified": "2026-09-11T10:00:00",
                }
            ]
        )
    )
    assert r == [
        {
            "nombre": "ppt_tmax_tmin_sg_2026",
            "url": "https://catalogodatos.gub.uy/x/ppt_tmax_tmin_sg_2026.csv",
            "formato": "CSV",
            "modificado": "2026-09-11T10:00:00",
        }
    ]


def test_success_falso_se_rechaza():
    with pytest.raises(CatalogoInvalido, match="success"):
        parsear_package_show({"success": False, "error": {"message": "Not found"}})


def test_dataset_sin_recursos_se_rechaza():
    with pytest.raises(CatalogoInvalido, match="recursos"):
        parsear_package_show(_respuesta([]))
