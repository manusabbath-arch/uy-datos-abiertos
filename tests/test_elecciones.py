"""Tests de `uydatos.elecciones`, sin red, con CSV sintéticos que tienen la forma de los reales.

Cada clase fija una trampa medida el 10/10/2026 (ver `docs/2026-10-10-datos-civicos.md`).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from uydatos.elecciones import (
    DEPARTAMENTOS,
    ELECCIONES,
    EleccionesInvalido,
    leer_desglose,
    leer_plan,
    leer_totales,
    normalizar_lema,
    resumen,
    votos_por_lema,
)


def _csv(tmp_path: Path, nombre: str, encabezado: str, filas: list[str]) -> Path:
    p = tmp_path / nombre
    p.write_text("﻿" + "\n".join([encabezado, *filas]) + "\n", encoding="utf-8")
    return p


TOTALES_2024 = (
    "Departamento,CRV,Serie,TotalHabilitados,TotalVotosEmitidos,TotalVotosNoObservados,"
    "TotalVotosObservados,TotalAnulados,TotalEnBlanco,TotalSoloSi,SiArt11,SiArt67"
)
BALOTAJE = (
    "Departamento,CRV,Serie,TotalHabilitados,TotalVotosEmitidos,TotalVotosNoObservados,"
    "TotalVotosObservados,TotalAnulados,TotalEnBlanco,TotalOrsiCosse,TotalDelgadoRipoll"
)
TOTALES_2025 = (
    "Departamento,Municipio,CRV,Serie,TotalHabilitados,TotalVotosEmitidos,TotalVotosNoObservados,"
    "TotalVotosObservados,TotalAnulados,TotalEnBlanco,TotalEnBlancoParcial"
)


class TestTotales:
    def test_lee_una_mesa_y_traduce_el_departamento(self, tmp_path):
        p = _csv(tmp_path, "t.csv", TOTALES_2024, ["SA,12,BAA,397,311,307,4,2,0,7,149,106"])
        (m,) = leer_totales(p)
        assert (m["departamento"], m["codigo_departamento"], m["crv"]) == ("SALTO", "SA", 12)
        assert (m["habilitados"], m["emitidos"], m["observados"]) == (397, 311, 4)
        assert m["opciones"] == {"TotalSoloSi": 7, "SiArt11": 149, "SiArt67": 106}

    def test_los_19_codigos_propios_de_la_corte(self):
        """`FD` es Florida y `FS` Flores; `RV` Rivera y `RO` Rocha: no es el ISO ni el del INE."""
        assert len(DEPARTAMENTOS) == 19
        assert (DEPARTAMENTOS["FD"], DEPARTAMENTOS["FS"], DEPARTAMENTOS["RV"]) == ("FLORIDA", "FLORES", "RIVERA")

    def test_un_codigo_desconocido_se_rechaza(self, tmp_path):
        p = _csv(tmp_path, "t.csv", TOTALES_2024, ["XX,1,AAA,1,1,1,0,0,0,0,0,0"])
        with pytest.raises(EleccionesInvalido, match="XX"):
            leer_totales(p)

    def test_una_mesa_repetida_se_rechaza(self, tmp_path):
        p = _csv(tmp_path, "t.csv", TOTALES_2024, ["MO,1,AAA,1,1,1,0,0,0,0,0,0", "MO,1,AAA,1,1,1,0,0,0,0,0,0"])
        with pytest.raises(EleccionesInvalido, match="repetida"):
            leer_totales(p)

    def test_departamentales_traen_municipio(self, tmp_path):
        p = _csv(
            tmp_path, "t.csv", TOTALES_2025, ["MO,B,1,AAA,395,291,287,4,3,9,7", "SA,SIN MUNICIPIO,2,BAA,10,9,9,0,0,0,0"]
        )
        a, b = leer_totales(p)
        assert (a["municipio"], b["municipio"]) == ("B", None)


class TestObservados:
    """En cada mesa común los votos por opción excluyen los observados; los observados se escrutan
    en mesas especiales (serie `?ZZ`, 0 habilitados y 0 emitidos). Medido en el balotaje 2024: 7.234
    mesas comunes y 114 de observados."""

    FILAS = ["MO,1,AAA,397,317,313,4,10,2,147,154", "MO,9001,BZZ,0,0,4,0,0,0,3,1"]

    def test_la_mesa_de_observados_se_reconoce(self, tmp_path):
        comun, especial = leer_totales(_csv(tmp_path, "b.csv", BALOTAJE, self.FILAS))
        assert (comun["tipo"], especial["tipo"]) == ("comun", "observados")

    def test_el_resumen_suma_las_dos_y_lo_declara(self, tmp_path):
        r = resumen(leer_totales(_csv(tmp_path, "b.csv", BALOTAJE, self.FILAS)))
        assert (r["mesas_comunes"], r["mesas_de_observados"]) == (1, 1)
        assert r["opciones"] == {"TotalOrsiCosse": 150, "TotalDelgadoRipoll": 155}
        assert (r["observados"], r["escrutados_en_mesas_de_observados"]) == (4, 4)
        assert r["en_mesas_comunes_las_opciones_excluyen_observados"] is True

    def test_mesas_comunes_con_mas_emitidos_que_habilitados_se_cuentan_no_se_corrigen(self, tmp_path):
        p = _csv(tmp_path, "b.csv", BALOTAJE, ["MO,1,AAA,10,12,8,4,0,0,4,4"])
        r = resumen(leer_totales(p))
        assert r["controles"]["mesas_comunes_con_mas_emitidos_que_habilitados"] == 1
        assert r["emitidos"] == 12

    def test_filtrar_por_departamento(self, tmp_path):
        p = _csv(tmp_path, "b.csv", BALOTAJE, ["MO,1,AAA,397,317,313,4,10,2,147,154", "SA,1,BAA,100,90,90,0,0,0,50,40"])
        r = resumen(leer_totales(p), "salto")
        assert (r["mesas"], r["habilitados"], r["participacion_pct"]) == (1, 100, 90.0)


DESGLOSE_2024 = "TipoRegistro,Departamento,CRV,Series,Lema,Descripcion1,CantidadVotos"
DESGLOSE_2025 = "TIPO_REGISTRO,DEPARTAMENTO,CRV,SERIES,LEMA,DESCRIPCION_1,DESCRIPCION_2,CANTIDAD_VOTOS"


class TestDesglose:
    def test_el_voto_a_un_partido_es_hoja_mas_lema(self, tmp_path):
        p = _csv(
            tmp_path,
            "d.csv",
            DESGLOSE_2024,
            [
                "HOJA_EN,MO,1,AAA,Partido Frente Amplio,609,100",
                "HOJA_EN,MO,1,AAA,Partido Frente Amplio,90,20",
                "VOTO_LEMA,MO,1,AAA,Partido Frente Amplio,609;90,3",
                "HOJA_EN,SA,1,BAA,Partido Nacional,40,50",
            ],
        )
        r = votos_por_lema(leer_desglose(p), "nacional")
        assert r[0] == {"lema": "Partido Frente Amplio", "votos": 123, "por_hoja": 120, "al_lema": 3}
        assert votos_por_lema(leer_desglose(p), "nacional", "Salto") == [
            {"lema": "Partido Nacional", "votos": 50, "por_hoja": 50, "al_lema": 0}
        ]

    def test_las_mesas_de_observados_se_pueden_dejar_afuera(self, tmp_path):
        """Lo repartible por circuito o localidad: sin las mesas de observados, que no tienen localidad."""
        filas = ["HOJA_EN,MO,1,AAA,Partido Frente Amplio,609,100", "HOJA_EN,MO,9001,BZZ,Partido Frente Amplio,609,7"]
        desglose = leer_desglose(_csv(tmp_path, "d.csv", DESGLOSE_2024, filas))
        assert votos_por_lema(desglose, "nacional")[0]["votos"] == 107
        assert votos_por_lema(desglose, "nacional", incluir_observados=False)[0]["votos"] == 100

    def test_columnas_en_mayusculas_de_2025_y_niveles(self, tmp_path):
        p = _csv(
            tmp_path,
            "d.csv",
            DESGLOSE_2025,
            [
                "HOJA_ED,MO,1,AAA,FRENTE AMPLIO,9,,4",
                "HOJA_EM,MO,1,AAA,FRENTE AMPLIO,53-B,B,8",
                "VOTO_LEMA_ED,MO,1,AAA,FRENTE AMPLIO,1;2,,1",
            ],
        )
        filas = leer_desglose(p)
        assert {f["nivel"] for f in filas} == {"departamental", "municipal"}
        assert votos_por_lema(filas, "departamental")[0]["votos"] == 5
        assert votos_por_lema(filas, "municipal")[0]["votos"] == 8

    def test_un_tipo_de_registro_desconocido_se_rechaza(self, tmp_path):
        p = _csv(tmp_path, "d.csv", DESGLOSE_2024, ["HOJA_XX,MO,1,AAA,X,1,1"])
        with pytest.raises(EleccionesInvalido, match="HOJA_XX"):
            leer_desglose(p)

    def test_normalizar_lema_para_comparar_elecciones(self):
        """«Partido Frente Amplio» (2024) y «FRENTE AMPLIO» (2025) son el mismo partido."""
        assert normalizar_lema("Partido Frente Amplio") == normalizar_lema("FRENTE AMPLIO") == "FRENTE AMPLIO"
        assert normalizar_lema("Partido Ecologista Radical Intransigente") == "ECOLOGISTA RADICAL INTRANSIGENTE"


PLAN_2024 = "Departamento,NroCircuito,Serie,Desde,Hasta,Localidad,Local ,Accesibilidad,TipoCircuito"
PLAN_2025 = "Departamento,Municipio,NroCircuito,Serie,Desde,Hasta,Localidad,Local ,Accesibilidad,TipoCircuito"


class TestPlan:
    def test_local_con_espacio_y_tipo_abreviado(self, tmp_path):
        p = _csv(tmp_path, "p.csv", PLAN_2024, ['SA,12,BAA,1,300,SALTO,"ESCUELA 1 - URUGUAY 100",S,U'])
        (c,) = leer_plan(p)
        assert (c["local"], c["tipo"], c["accesible"], c["departamento"]) == (
            "ESCUELA 1 - URUGUAY 100",
            "urbano",
            True,
            "SALTO",
        )

    def test_tipo_con_palabra_de_2025(self, tmp_path):
        p = _csv(tmp_path, "p.csv", PLAN_2025, ["SA,SIN MUNICIPIO,40,BAA,1,90,COLONIA LAVALLEJA,ESCUELA 9,N,RURAL"])
        (c,) = leer_plan(p)
        assert (c["tipo"], c["accesible"], c["municipio"]) == ("rural", False, None)

    def test_tipo_desconocido_se_rechaza(self, tmp_path):
        p = _csv(tmp_path, "p.csv", PLAN_2024, ["SA,1,BAA,1,2,SALTO,X,S,Z"])
        with pytest.raises(EleccionesInvalido, match="Z"):
            leer_plan(p)


class TestDeclaracion:
    def test_ninguna_eleccion_lee_la_integracion_de_hojas(self):
        """La integración trae la credencial cívica de cada candidato: este paquete no la lee."""
        for e in ELECCIONES.values():
            assert all("integracion" not in prefijo for prefijo in e["archivos"].values())
