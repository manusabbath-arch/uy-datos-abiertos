"""Tests de `uydatos.parlamento`, sin red, con CSV sintéticos que tienen la forma de los reales.

Cada clase fija algo medido el 10/10/2026 (ver `docs/2026-10-10-datos-civicos.md`, §4).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from uydatos import parlamento
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


# --- Pedidos de informes y nómina -------------------------------------------------------------

PEDIDOS = (
    "Organismo,Fecha,Autores,Tema,Estado,URLoficio,URLcontestacion\n"
    "MINISTERIO DE SALUD PÚBLICA,2025/03/01,Gustavo Salle Lorier,TEMA A,CONTESTADO,https://x/o1.pdf,https://x/c1.pdf\n"
    "MINISTERIO DE SALUD PÚBLICA,2025/03/01,Gustavo Salle Lorier,TEMA A,CONTESTADO,https://x/o2.pdf,\n"
    "MINISTERIO DE TRANSPORTE Y OBRAS PÚBLICAS,2025/04/10,José Luis Satdjian +  Amin Niffouri,TEMA B,VENCIDO,https://x/o3.pdf,\n"
    "MINISTERIO DE TRANSPORTE Y OBRAS PÚBLICAS,2026/09/20,Persona Desconocida,TEMA C,SIN CONTESTAR,https://x/o4.pdf,\n"
)
NOMINA = (
    "Nombre,Genero,Edad,PartidoPolitico,Departamento,HojaVotacion\n"
    '"SALLE LORIER, GUSTAVO ",Varón,70,Identidad Soberana,Montevideo,1.0\n'
    '"SATDJIAN ALVAREZ, JOSÉ LUIS",Varón,45,Nacional,Montevideo,71.0\n'
    '"NIFFOURI BLANCO, AMIN",Varón,50,Nacional,Canelones,404.0\n'
)


@pytest.fixture
def pedidos_y_nomina(tmp_path):
    (tmp_path / "p.csv").write_text(PEDIDOS, encoding="utf-8")
    (tmp_path / "n.csv").write_text(NOMINA, encoding="utf-8")
    return parlamento.leer_pedidos(tmp_path / "p.csv"), parlamento.leer_nomina(tmp_path / "n.csv")


class TestPedidos:
    def test_lee_coautores_separados_por_mas(self, pedidos_y_nomina):
        pedidos, _ = pedidos_y_nomina
        assert pedidos[2]["autores"] == ["José Luis Satdjian", "Amin Niffouri"]
        assert pedidos[1]["url_contestacion"] is None and pedidos[0]["fecha"].isoformat() == "2025-03-01"

    def test_la_nomina_no_lee_la_edad(self, pedidos_y_nomina):
        _, nomina = pedidos_y_nomina
        assert nomina[0] == {
            "nombre": "SALLE LORIER, GUSTAVO",
            "partido": "Identidad Soberana",
            "departamento": "Montevideo",
            "hoja": 1,
        }

    def test_identificar_exige_un_unico_candidato(self, pedidos_y_nomina):
        _, nomina = pedidos_y_nomina
        assert parlamento.identificar("José Luis Satdjian", nomina)["partido"] == "Nacional"
        assert parlamento.identificar("Persona Desconocida", nomina) is None
        doble = nomina + [{"nombre": "SALLE PEREZ, GUSTAVO", "partido": "X", "departamento": "", "hoja": None}]
        assert parlamento.identificar("Gustavo Salle", doble) is None

    def test_la_tasa_es_sobre_los_que_cumplieron_el_plazo(self, pedidos_y_nomina):
        pedidos, nomina = pedidos_y_nomina
        r = parlamento.resumen_pedidos(pedidos, date(2026, 10, 11), nomina)
        # el de 2026/09/20 tiene 21 días: no entra en la tasa
        assert r["total"]["con_plazo_cumplido"] == 3 and r["total"]["pct_contestado_con_plazo_cumplido"] == 66.7
        mtop = next(o for o in r["por_organismo"] if "TRANSPORTE" in o["organismo"])
        assert mtop["pedidos"] == 2 and mtop["pct_contestado_con_plazo_cumplido"] == 0.0
        assert r["contestados_sin_enlace"] == 1 and r["con_varios_autores"] == 1 and r["repetidos"] == 1

    def test_un_pedido_con_dos_autores_del_mismo_partido_cuenta_una_vez(self, pedidos_y_nomina):
        pedidos, nomina = pedidos_y_nomina
        r = parlamento.resumen_pedidos(pedidos, date(2026, 10, 11), nomina)
        assert r["pedidos_por_partido"] == {"Identidad Soberana": 2, "Nacional": 1}
        assert r["autores_sin_identificar"] == {"Persona Desconocida": 1}

    def test_cohorte_y_semestres(self, pedidos_y_nomina):
        pedidos, _ = pedidos_y_nomina
        r = parlamento.resumen_pedidos(pedidos, date(2026, 10, 11), presentados_hasta=date(2025, 12, 31))
        assert r["total"]["pedidos"] == 3 and [s["semestre"] for s in r["por_semestre"]] == ["2025-S1"]

    def test_un_estado_que_no_se_midio_se_rechaza(self, tmp_path):
        (tmp_path / "p.csv").write_text(PEDIDOS.replace("VENCIDO", "ARCHIVADO"), encoding="utf-8")
        with pytest.raises(parlamento.ParlamentoInvalido, match="ARCHIVADO"):
            parlamento.leer_pedidos(tmp_path / "p.csv")

    def test_una_fecha_en_otro_formato_se_rechaza(self, tmp_path):
        (tmp_path / "p.csv").write_text(PEDIDOS.replace("2025/04/10", "10/04/2025"), encoding="utf-8")
        with pytest.raises(parlamento.ParlamentoInvalido, match="AAAA/MM/DD"):
            parlamento.leer_pedidos(tmp_path / "p.csv")
