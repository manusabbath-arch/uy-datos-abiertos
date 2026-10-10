"""Tests de `uydatos.parlamento`, sin red, con CSV sintéticos que tienen la forma de los reales.

Cada clase fija algo medido el 10/10/2026 (ver `docs/2026-10-10-datos-civicos.md`, §4).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from uydatos.parlamento import (
    ParlamentoInvalido,
    leer_asistencias,
    leer_leyes,
    leer_proyectos,
    legislatura_del_titulo,
    resumen_asistencias,
)

ASISTENCIAS = (
    "Nombre,Citaciones,Asistencias,Porcentaje de asistencias,Faltas c/Aviso\t,Porcentaje de faltas,"
    "Cantidad de faltas sin aviso,Porcentaje de faltas s/ aviso,No citado por Licencia,"
    "Pasajes a Presidente de la República"
)


def _csv(tmp_path: Path, encabezado: str, filas: list[str], nombre: str = "a.csv") -> Path:
    p = tmp_path / nombre
    p.write_text("\ufeff" + "\n".join([encabezado, *filas]) + "\n", encoding="utf-8")
    return p


class TestAsistencias:
    def test_lee_y_calcula_el_porcentaje(self, tmp_path):
        p = _csv(tmp_path, ASISTENCIAS, ['"Abdala, Pablo",364,348,96,10,3,6,2,4,0'])
        (f,) = leer_asistencias(p)
        assert f == {
            "nombre": "Abdala, Pablo",
            "citaciones": 364,
            "asistencias": 348,
            "faltas_con_aviso": 10,
            "faltas_sin_aviso": 6,
            "licencias": 4,
            "pasajes_a_presidente": 0,
            "pct_asistencia": 95.6,
        }

    def test_la_columna_con_tabulador_pegado(self, tmp_path):
        """`'Faltas c/Aviso\\t'`: la columna trae un tabulador en el nombre."""
        p = _csv(tmp_path, ASISTENCIAS, ['"X, Y",10,9,90,1,10,0,0,0,0'])
        assert leer_asistencias(p)[0]["faltas_con_aviso"] == 1

    def test_citaciones_que_no_cierran_se_rechazan(self, tmp_path):
        """Medido: citaciones = asistencias + faltas con y sin aviso en las 10 legislaturas, sin excepción."""
        p = _csv(tmp_path, ASISTENCIAS, ['"X, Y",10,5,50,1,10,1,10,0,0'])
        with pytest.raises(ParlamentoInvalido, match="citaciones"):
            leer_asistencias(p)

    def test_una_fila_sin_nombre_se_lee_con_nombre_none(self, tmp_path):
        """Diputados 49 y 50 traen filas con nombre `","`: hay citaciones de alguien sin nombre."""
        p = _csv(tmp_path, ASISTENCIAS, ['",",25,25,100,0,0,0,0,0,0'])
        assert leer_asistencias(p)[0]["nombre"] is None

    def test_los_homonimos_no_se_unen(self, tmp_path):
        """El archivo no trae identificador: dos filas con el mismo nombre quedan como dos."""
        p = _csv(tmp_path, ASISTENCIAS, ['"Pérez, Julio",1,1,100,0,0,0,0,0,0', '"Pérez, Julio",45,44,98,1,2,0,0,0,0'])
        assert len(leer_asistencias(p)) == 2


class TestResumen:
    def _filas(self, tmp_path):
        return leer_asistencias(
            _csv(
                tmp_path,
                ASISTENCIAS,
                [
                    '"Titular, Uno",300,240,80,30,10,30,10,0,0',
                    '"Titular, Dos",300,297,99,3,1,0,0,0,0',
                    '"Suplente, Tres",2,0,0,2,100,0,0,0,0',
                    '"Pérez, Julio",1,1,100,0,0,0,0,0,0',
                    '"Pérez, Julio",45,44,98,1,2,0,0,0,0',
                    '",",4,4,100,0,0,0,0,0,0',
                ],
            )
        )

    def test_el_minimo_de_citaciones_saca_a_los_suplentes_de_paso(self, tmp_path):
        """Con 2 citaciones, 0% no dice nada: el ranking necesita un mínimo."""
        r = resumen_asistencias(self._filas(tmp_path), minimo_citaciones=10)
        assert [f["nombre"] for f in r["menor_asistencia"]][:2] == ["Titular, Uno", "Pérez, Julio"]
        assert r["fuera_por_pocas_citaciones"] == 2  # la fila sin nombre se cuenta aparte

    def test_declara_homonimos_y_filas_sin_nombre(self, tmp_path):
        r = resumen_asistencias(self._filas(tmp_path))
        assert r["nombres_repetidos"] == ["Pérez, Julio"] and r["filas_sin_nombre"] == 1
        assert r["personas"] == 6

    def test_buscar_por_nombre_sin_tildes(self, tmp_path):
        r = resumen_asistencias(self._filas(tmp_path), nombre="perez")
        assert [f["citaciones"] for f in r["encontrados"]] == [1, 45]


PROYECTOS = "Fecha,Asunto,Carpetas,Titulo"


class TestProyectos:
    def test_tipo_y_carpetas(self, tmp_path):
        p = _csv(
            tmp_path,
            PROYECTOS,
            [
                '2026-10-07,175435,"CSS   : 696 / 2026,  CRR  : 12 / 2026",'
                '"TÍTULOS ELECTRÓNICOS. Se reconoce su valor (PROYECTO DE LEY)"'
            ],
        )
        (f,) = leer_proyectos(p)
        assert f["tipo"] == "PROYECTO DE LEY" and f["asunto"] == 175435
        assert f["carpetas"] == [
            {"organo": "CSS", "numero": 696, "anio": 2026},
            {"organo": "CRR", "numero": 12, "anio": 2026},
        ]
        assert f["titulo"] == "TÍTULOS ELECTRÓNICOS. Se reconoce su valor"

    def test_sin_carpeta(self, tmp_path):
        p = _csv(tmp_path, PROYECTOS, ['2026-10-07,1,,"X (PROYECTO DE RESOLUCION)"'])
        assert leer_proyectos(p)[0]["carpetas"] == []

    def test_asunto_repetido_dentro_de_un_archivo_se_rechaza(self, tmp_path):
        p = _csv(tmp_path, PROYECTOS, ['2026-10-07,1,,"X (PROYECTO DE LEY)"', '2026-10-08,1,,"Y (PROYECTO DE LEY)"'])
        with pytest.raises(ParlamentoInvalido, match="repetido"):
            leer_proyectos(p)


LEYES = "Fecha,Numero_de_Ley,Texto_Original,Texto_Actualizado,Titulo,Asunto,Leyes_Referenciadas,Leyes_que_referencia"


class TestLeyes:
    def _p(self, tmp_path, filas):
        return _csv(tmp_path, LEYES, filas)

    def test_lee_una_ley(self, tmp_path):
        p = self._p(tmp_path, ["2026-10-01,20531,https://p/20531,https://impo/20531,RENDICIÓN DE CUENTAS.,173797,2,0"])
        r = leer_leyes(p)
        (ley,) = r["leyes"]
        assert (ley["numero"], ley["texto_impo"], ley["cantidad_que_cita"], ley["cantidad_que_la_citan"]) == (
            20531,
            "https://impo/20531",
            2,
            0,
        )

    def test_duplicadas_exactas_y_ley_cero_aparte(self, tmp_path):
        """Medido: 2 filas duplicadas exactas y una «ley 0» (una pensión graciable de 1997)."""
        filas = [
            "2009-09-11,18547,u,v,CONVENIO.,36961,0,0",
            "2009-09-11,18547,u,v,CONVENIO.,36961,0,0",
            "1997-05-07,0,u,v,PENSION GRACIABLE.,1,0,0",
            "2009-09-12,18548,u,v,OTRA.,36962,0,0",
        ]
        r = leer_leyes(self._p(tmp_path, filas))
        assert [x["numero"] for x in r["leyes"]] == [18547, 18548]
        assert r["duplicadas"] == 1 and len(r["sin_numero"]) == 1
        assert r["faltantes"] == []

    def test_los_numeros_que_faltan_se_informan(self, tmp_path):
        filas = ["2009-09-11,100,u,v,A.,1,0,0", "2009-09-12,103,u,v,B.,2,0,0"]
        assert leer_leyes(self._p(tmp_path, filas))["faltantes"] == [101, 102]

    def test_un_mismo_numero_con_dos_contenidos_se_rechaza(self, tmp_path):
        filas = ["2009-09-11,100,u,v,A.,1,0,0", "2009-09-11,100,u,v,B.,2,0,0"]
        with pytest.raises(ParlamentoInvalido, match="100"):
            leer_leyes(self._p(tmp_path, filas))


class TestTitulos:
    def test_legislatura_del_titulo(self):
        assert legislatura_del_titulo("Asistencias a Sesiones de Cámara  - Legislatura 50") == 50
        assert legislatura_del_titulo("Proyectos al Parlamento - Legislatura 42") == 42
        assert legislatura_del_titulo("Metadatos") is None
