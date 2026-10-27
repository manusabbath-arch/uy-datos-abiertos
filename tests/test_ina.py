"""Tests del lector de nivel y caudal del río Uruguay del INA (sin red, salvo los marcados `red`)."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from uydatos import ina, red
from uydatos.ina import InaInvalido

ENCABEZADO = "id,tipo,series_id,timestart,timeend,nombre,descripcion,unit_id,timeupdate,valor"

# Filas reales del API, medidas el 2026-10-27: las diarias de la 77/926 (03:00Z = 00:00 UY) y una
# fila legítima de la 79 con la columna `nombre` vacía (la hora de la lectura del operador, no
# un defecto: 2 de 37.876 en el archivo completo son así).
REAL = {
    77: [
        "29528185196,puntual,77,2026-10-23T03:00:00.000Z,2026-10-23T03:00:00.000Z,upsertObservacionesPuntual,,,"
        "2026-10-23T14:32:35.256Z,35.06",
        "29539260580,puntual,77,2026-10-24T03:00:00.000Z,2026-10-24T03:00:00.000Z,upsertObservacionesPuntual,,,"
        "2026-10-24T16:33:30.641Z,34.92",
        "29559364206,puntual,77,2026-10-26T03:00:00.000Z,2026-10-26T03:00:00.000Z,upsertObservacionesPuntual,,,"
        "2026-10-26T15:43:15.114Z,34.7",
    ],
    79: [
        "22884161281,puntual,79,2024-10-23T19:00:00.000Z,2024-10-23T19:00:00.000Z,,,,2024-10-24T14:10:31.072Z,6.04",
    ],
    926: [
        "29497935513,puntual,926,2026-10-20T03:00:00.000Z,2026-10-20T03:00:00.000Z,upsertObservacionesPuntual,,,"
        "2026-10-20T15:01:46.768Z,17962",
    ],
}


def _archivo(p: Path, sid: int = 77, filas=None, encabezado: str = ENCABEZADO) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join([encabezado, *(REAL[sid] if filas is None else filas)]) + "\n", encoding="utf-8")
    return p


# ------------------------------------------------------------ lectura


def test_lee_y_tipa_el_instante_la_carga_y_la_unidad(tmp_path):
    filas = ina.observaciones(77, date(2026, 10, 20), date(2026, 10, 27), crudo=_archivo(tmp_path / "serie_77.csv"))
    assert [f["valor"] for f in filas] == [35.06, 34.92, 34.7]
    assert filas[0]["var"] == "H" and filas[0]["unidad"] == "m"
    assert filas[0]["instancia"] == datetime(2026, 10, 23, 3, 0, tzinfo=timezone.utc)
    assert filas[0]["carga"] == datetime(2026, 10, 23, 14, 32, 35, 256000, tzinfo=timezone.utc)
    # 03:00Z = 00:00 UY: el día local es el mismo
    assert filas[0]["dia_local"] == date(2026, 10, 23)


def test_la_fila_sin_nombre_es_dato_legitimo(tmp_path):
    # La columna `nombre` está vacía en 2 de las 37.876 filas medidas de la serie 79 y el valor
    # está bien puesto: no se rechaza, se lee como la filas demás.
    filas = ina.observaciones(79, date(2024, 10, 20), date(2024, 10, 25), crudo=_archivo(tmp_path / "serie_79.csv", 79))
    assert filas[0]["nombre_fuente"] == "" and filas[0]["valor"] == 6.04
    assert filas[0]["instancia"].hour == 19 and filas[0]["instancia"].minute == 0
    assert ina.resumen(filas)["nombre_inesperado"] == 0


def test_el_dia_local_es_funcion_con_el_desfase_como_parametro(tmp_path):
    # 52 de 37.876 filas del histórico están a las 00-02Z: su día uruguayo es el anterior. El
    # desfase va como parámetro porque es política del consumidor, no una constante del lector.
    inst = datetime(2024, 10, 24, 2, 0, tzinfo=timezone.utc)  # 02:00Z
    assert ina.dia_local(inst) == date(2024, 10, 23)
    assert ina.dia_local(inst, desfase_horas=0) == date(2024, 10, 24)
    filas = ina.observaciones(79, date(2024, 10, 20), date(2024, 10, 25), crudo=_archivo(tmp_path / "x.csv", 79))
    assert filas[0]["dia_local"] == ina.dia_local(filas[0]["instancia"], desfase_horas=-3)


# ------------------------------------------------------------ rechazar en vez de arreglar


@pytest.mark.parametrize(
    "rota,esperado",
    [
        ("tipo", "fuera del dominio"),
        ("series_id", "series_id ilegible"),
        ("timestart", "timestart ilegible"),
        ("timeupdate", "timeupdate ilegible"),
        ("valor", "valor ilegible"),
    ],
)
def test_un_campo_ilegible_rechaza_con_el_motivo(tmp_path, rota, esperado):
    fila = REAL[77][0].split(",")
    idx = ENCABEZADO.split(",").index(rota)
    fila[idx] = "mal"
    p = _archivo(tmp_path / "m.csv", 77, [",".join(fila)])
    with pytest.raises(InaInvalido, match=esperado):
        ina.observaciones(77, date(2026, 10, 20), date(2026, 10, 27), crudo=p)


def test_serie_no_declarada_rechaza(tmp_path):
    with pytest.raises(InaInvalido, match="no está declarada"):
        ina.observaciones(9999, date(2026, 10, 1), date(2026, 10, 10))


def test_serie_declarada_con_otro_id_en_el_cuerpo_rechaza(tmp_path):
    # La estación 283 "CONCORDIA (DNCPVN-61…)" es de Brasil y por el nombre se la puede leer
    # como si fuera la Concordia del río (la 79): el lector valida que cada fila sea de la serie
    # pedida, no se fía del nombre del recurso.
    fila = REAL[79][0].split(",")
    fila[2] = "999"
    p = _archivo(tmp_path / "serie_79.csv", 79, [",".join(fila)])
    with pytest.raises(InaInvalido, match="series_id 999 distinto del pedido"):
        ina.observaciones(79, date(2024, 10, 20), date(2024, 10, 25), crudo=p)


def test_fila_fuera_del_rango_pedido_rechaza(tmp_path):
    # El API respeta el filtro (medido: con timeend 2015 la última fila es del 31/12/2015), pero
    # se valida igual: una fila fuera del rango pedido es la fuente dejando de comportarse.
    p = _archivo(tmp_path / "serie_77.csv", 77)
    with pytest.raises(InaInvalido, match="fuera del rango pedido"):
        ina.observaciones(77, date(2031, 1, 1), date(2035, 12, 31), crudo=p)


def test_rango_invalido_no_sale_a_la_red(tmp_path, monkeypatch):
    # El API responde 200 con cuerpo vacío a timestart > timeend (medido): se valida antes.
    def no_salir(*a, **k):  # pragma: no cover - si se llega acá, el test está roto
        raise AssertionError("no debía salir a la red con un rango inválido")

    monkeypatch.setattr(red, "pedir", no_salir)
    with pytest.raises(InaInvalido, match="rango inválido"):
        ina.observaciones(77, date(2026, 10, 27), date(2026, 10, 20))


def test_cuerpo_vacio_de_una_serie_viva_rechaza(tmp_path, monkeypatch):
    # El API responde 200 con cuerpo vacío (ni encabezado) a la serie 938 "Aporte Salto Grande"
    # (has_obs false, medido): una serie sin filas no es un dato y no escribe nada a medias.
    monkeypatch.setattr(red, "pedir", lambda *a, **k: b"")
    with pytest.raises(InaInvalido, match="cuerpo vacío"):
        ina.observaciones(77, date(2026, 10, 1), date(2026, 10, 10))


def test_encabezado_nuevo_rechaza_y_no_inventa_columnas(tmp_path):
    p = _archivo(tmp_path / "serie_77.csv", 77, encabezado=ENCABEZADO.replace(",descripcion", ""))
    with pytest.raises(InaInvalido, match="encabezado inesperado"):
        ina.observaciones(77, date(2026, 10, 20), date(2026, 10, 27), crudo=p)


def test_valor_fuera_del_rango_fisico_rechaza(tmp_path):
    # El rango del H es -10 a 60 m (95 años medidos: -0,24 a 17,82). Un 999 de Concordia no es
    # un dato raro a declarar: es un defecto de la fuente y para el archivo completo.
    p = _archivo(
        tmp_path / "serie_77.csv",
        77,
        [
            "29559364206,puntual,77,2026-10-26T03:00:00.000Z,2026-10-26T03:00:00.000Z,upsertObservacionesPuntual,,,"
            "2026-10-26T15:43:15.114Z,999",
        ],
    )
    with pytest.raises(InaInvalido, match="fuera del rango físico"):
        ina.observaciones(77, date(2026, 10, 20), date(2026, 10, 27), crudo=p)


def test_valor_vacio_rechaza(tmp_path):
    # El API no trae filas con el valor vacío (0 de 37.876): los huecos son filas que no
    # existen. Una fila con el valor vacío no es "0" ni "sin dato": es un cambio del dominio.
    fila = REAL[77][0].split(",")
    fila[9] = ""
    p = _archivo(tmp_path / "serie_77.csv", 77, [",".join(fila)])
    with pytest.raises(InaInvalido, match="valor vacío"):
        ina.observaciones(77, date(2026, 10, 20), date(2026, 10, 27), crudo=p)


def test_timeend_distinto_de_timestart_rechaza(tmp_path):
    # En las 37.876 filas medidas, timestart == timeend. Si algún día el API devuelve una fila
    # con intervalo (una serie agregada), el lector no la cuela como puntual.
    fila = REAL[77][0].split(",")
    fila[4] = "2026-10-23T06:00:00.000Z"
    p = _archivo(tmp_path / "serie_77.csv", 77, [",".join(fila)])
    with pytest.raises(InaInvalido, match="timeend"):
        ina.observaciones(77, date(2026, 10, 20), date(2026, 10, 27), crudo=p)


# ------------------------------------------------------------ resumen y sello


def test_resumen_declara_los_extremos_y_la_frescura(tmp_path):
    filas = ina.observaciones(77, date(2026, 10, 20), date(2026, 10, 27), crudo=_archivo(tmp_path / "x.csv", 77))
    r = ina.resumen(filas)
    assert r["filas"] == 3 and r["series_distintas"] == 1
    s = r["series"][77]
    assert (s["min"], s["max"]) == (34.7, 35.06)
    assert s["unidad"] == "m"
    assert s["primer_dia"] == date(2026, 10, 23) and s["ultimo_dia"] == date(2026, 10, 26)
    # la frescura es del `timeupdate`, no de la fila: la última carga del API manda
    assert s["ultima_carga"] == datetime(2026, 10, 26, 15, 43, 15, 114000, tzinfo=timezone.utc)


def test_resumen_cuenta_los_dias_con_dos_lecturas(tmp_path):
    # 2.524 de los 34.932 días del histórico traen 2 lecturas: dos filas del mismo día local es
    # la regla, no una anomalía; resumen() la cuenta para que se vea en el informe. La fila
    # legítima del historial (19:00Z) y una fabricada a las 02:00Z del día siguiente: ambas caen
    # en el 23/10 en hora de Uruguay.
    dos = [
        "22884161281,puntual,79,2024-10-23T19:00:00.000Z,2024-10-23T19:00:00.000Z,,,,2024-10-24T14:10:31.072Z,6.04",
        "22884161282,puntual,79,2024-10-24T02:00:00.000Z,2024-10-24T02:00:00.000Z,,,,2024-10-24T14:10:31.072Z,6.1",
    ]
    filas = ina.observaciones(79, date(2024, 10, 20), date(2024, 10, 26), crudo=_archivo(tmp_path / "x.csv", 79, dos))
    r = ina.resumen(filas)
    assert r["series"][79]["dias_con_mas_de_una_lectura"] == 1
    assert Counter(f["dia_local"] for f in filas)[date(2024, 10, 23)] == 2


def test_sello_lleva_la_url_real_y_el_sha256(tmp_path):
    p = _archivo(tmp_path / "serie_77.csv", 77)
    s = ina.sello(77, p, desde=date(2026, 10, 20), hasta=date(2026, 10, 27), filas=3)
    assert s["url"] is not None and "series_id=77" in s["url"] and "timestart=2026-10-20" in s["url"]
    assert s["sha256"] and len(s["sha256"]) == 64 and s["filas"] == 3
    assert "INA a5" in s["fuente"]


def test_url_sin_red_con_los_params_de_hora_uy():
    url = ina.url_observaciones(77, date(2026, 10, 20), date(2026, 10, 27))
    assert url.endswith("timestart=2026-10-20T00:00:00.000-03:00&timeend=2026-10-27T23:59:59.000-03:00")
    assert "series/77/observaciones" in url and "format=csv" in url


def test_descarga_arma_las_urls_de_las_seis_series(tmp_path, monkeypatch):
    # El `timeend` va hasta HOY en hora de Uruguay y el `desde` N días atrás: el que consume
    # decide la frescura contra `timeupdate`, contra el reloj del sello. El hoy UY se calcula
    # igual que la herramienta (lo que el runner esté en UTC no cambia la URL que se aserta).
    pedidos = []

    def fake_bajar(url, destino, **k):
        pedidos.append(url)
        Path(destino).write_text(ENCABEZADO + "\n", encoding="utf-8")
        return Path(destino)

    monkeypatch.setattr(red, "bajar", fake_bajar)
    ina.descargar(tmp_path, dias=10)
    assert len(pedidos) == 6
    for url in pedidos:
        assert (
            "timeend=" + (datetime.now(timezone.utc) - timedelta(hours=3)).date().isoformat() + "T23:59:59.000-03:00"
            in url
        )


# ------------------------------------------------------------ contra la fuente real (se corre con -m red)


@pytest.mark.red
def test_red_las_series_frescas_traen_el_dato_diario():
    """Ventana de 10 días atrás a anteayer: las series diarias del canal traen el dato.

    El número: el dato del día se carga entre las 12:43 y las 18:01 UY (medido el 2026-10-27),
    así que hasta la anteayer SIEMPRE hay filas; de hoy no se afirma nada (el dato puede no
    estar). La serie 928 no va acá: se midió con 3,5 meses de atraso y tiene su prueba abajo."""
    hoy = ina.dia_local(datetime.now(timezone.utc))
    desde, hasta = hoy - timedelta(days=10), hoy - timedelta(days=2)
    for sid in (77, 78, 79, 926, 927):
        filas = ina.observaciones(sid, desde, hasta)
        assert len(filas) >= 5, f"serie {sid}: {len(filas)} filas en {desde}-{hasta}"
        assert max(f["valor"] for f in filas) <= ina.RANGO_FISICO[ina.SERIES[sid]["var"]][1]
        ultimo = max(f["dia_local"] for f in filas)
        assert desde <= ultimo <= hasta, f"serie {sid}: última lectura {ultimo}"


@pytest.mark.red
def test_red_la_serie_atrasada_sigue_siendo_leible():
    """El caudal de Concordia (928) se midió con 3,5 meses de atraso (última fila 15/07/2026) y
    el API responde cuerpo vacío a su ventana reciente.

    La prueba es de que la serie sigue respondiendo con su historia, no de que esté al día: la
    ventana va de 400 a 200 días atrás, donde la serie trae sus filas —medido el 2026-10-27:
    136 lecturas, con sus huecos—. Si la INA la actualiza al día, el número sube y se anota; si
    la serie deja de responder, esta prueba lo dice en lugar del consumo por sorpresa."""
    hoy = ina.dia_local(datetime.now(timezone.utc))
    filas = ina.observaciones(928, hoy - timedelta(days=400), hoy - timedelta(days=200))
    assert len(filas) >= 100, len(filas)


@pytest.mark.red
def test_red_rango_cerrado_de_95_anios_trae_el_contrato_medido():
    """1931-1935 de la serie 79 (Concordia): 1.826 filas, el número medido el 2026-10-27.

    Es la prueba que dice si el histórico completo sigue respondiendo con una fila por lectura
    y órden ascendente. Si cambió, se anota el nuevo número con la causa: una API que deja de
    devolver su histórica es un cambio de la fuente, no un redondeo."""
    filas = ina.observaciones(79, date(1931, 1, 1), date(1935, 12, 31))
    assert len(filas) == 1826, len(filas)
    assert filas[0]["instancia"].year == 1931
    assert [f["instancia"] for f in filas] == sorted(f["instancia"] for f in filas)


@pytest.mark.red
def test_red_metadata_de_concordia_es_la_del_rio_y_no_la_de_brasil():
    """La metadata de la serie 79: país Argentina, escalas de Prefectura Nacional y alerta 11 m.

    La trampa: la estación 283 "CONCORDIA (DNCPVN-61…)" es de Brasil (red_ana_hidro, id_externo
    78500000). Fijar una serie por nombre y no por id trae el dato de otra red sin avisarlo."""
    m = ina.metadata(79)
    assert m["estacion_id"] == 79 and m["pais"] == "Argentina" and m["nivel_alerta"] == 11
    assert m["red"] == "escalas Prefectura Nacional"
    assert m["var"] == "H" and m["unidad"] == "m"
