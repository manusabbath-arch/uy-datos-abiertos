"""Tests del lector de calidad de agua potable de OSE, sin red (salvo los marcados `red`)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from uydatos import catalogo, ose
from uydatos.ose import OseInvalido

ENCABEZADO = "ANIO;TRIMESTRE;DEPARTAMENTO;LOCALIDAD;LABORATORIO;AREA_ANALISIS;PARAMETRO;METODO;ID_MUESTRA_M;VALOR"

# Una fila de cada forma medida en el archivo real: coma, punto (Montevideo), censura a izquierda,
# censura con el signo al revés, las tres categorías de bacteriología y la misma muestra en dos
# laboratorios.
def _cruda(anio, tri, loc, lab, area, param, muestra, valor, dpto=None):
    campos = [str(anio), f"trimestre {tri}", dpto or loc, loc, lab, area, param, "metodo", muestra, valor]
    return ";".join(f'"{c}"' for c in campos)


FQ, BA = "FISICOQUÍMICO", "BACTERIOLOGÍA"
PAY, CEN = "Lab.Reg. Paysandú", "Laboratorio Central"
FILAS = [
    _cruda(2025, 1, "Salto", PAY, FQ, "PH", "M1", "6,8"),
    _cruda(2025, 1, "Montevideo", CEN, FQ, "PH", "M2", "6.9"),
    _cruda(2025, 4, "Salto", PAY, FQ, "COLOR VERDADERO", "M1", "<5"),
    _cruda(2017, 2, "Rivera", "Lab. Reg. Tacuarembo", FQ, "TURBIDEZ", "M3", ">0,2"),
    _cruda(2025, 2, "Salto", PAY, FQ, "OLOR", "M1", "Característico"),
    _cruda(2025, 3, "Salto", PAY, BA, "COLIFORMES TOTALES", "M4", "Ausencia"),
    _cruda(2025, 3, "Salto", CEN, BA, "ESCHERICHIA COLI", "M4", "Presencia"),
    _cruda(2020, 2, "Atlántida - Laguna del Cisne", CEN, BA, "COLIFORMES TOTALES", "M5", "<1", "Canelones"),
]


def _escribir(p: Path, filas=None) -> Path:
    p.write_text("\n".join([ENCABEZADO, *(FILAS if filas is None else filas)]) + "\n", encoding="utf-8")
    return p


def test_lee_las_dos_formas_de_separador_decimal(tmp_path):
    # El archivo real trae 98.215 pH con coma y 35.070 con punto, y el punto es casi todo
    # Montevideo. Un lector que acepte una sola forma pierde el 26% de las lecturas sin dar error.
    filas = ose.leer(_escribir(tmp_path / "ose.csv"))
    ph = {f["localidad"]: f for f in filas if f["parametro"] == "PH"}
    assert ph["Salto"]["valor"] == 6.8
    assert ph["Montevideo"]["valor"] == 6.9
    assert ph["Salto"]["punto_decimal"] is False
    assert ph["Montevideo"]["punto_decimal"] is True


def test_un_tercer_formato_de_numero_se_rechaza(tmp_path):
    p = _escribir(tmp_path / "ose.csv", [FILAS[0].replace('"6,8"', '"6·8"')])
    with pytest.raises(OseInvalido, match="valor ilegible"):
        ose.leer(p)


def test_el_limite_de_deteccion_no_se_confunde_con_una_medicion(tmp_path):
    # 124.424 de 132.745 valores de color son «<5» o «<2,5»: si el límite se guardara como
    # medición, el 93,7% de la serie serían números que nadie midió.
    color = next(f for f in ose.leer(_escribir(tmp_path / "ose.csv")) if f["parametro"] == "COLOR VERDADERO")
    assert (color["valor"], color["condicion"], color["unidad"]) == (5.0, "menor_que", "UC")


def test_el_signo_al_reves_se_devuelve_tal_cual(tmp_path):
    # Cuatro filas en 531.679 traen «>0,2» o «>5», el mismo número que el límite de detección de su
    # columna: casi seguro un error de carga. El lector no lo da vuelta.
    filas = ose.leer(_escribir(tmp_path / "ose.csv"))
    turb = next(f for f in filas if f["parametro"] == "TURBIDEZ")
    assert (turb["valor"], turb["condicion"]) == (0.2, "mayor_que")
    assert ose.resumen(filas)["censurados_al_reves"] == 1


def test_la_bacteriologia_no_se_convierte_a_numero(tmp_path):
    filas = ose.leer(_escribir(tmp_path / "ose.csv"))
    bact = [f for f in filas if f["area"] == "BACTERIOLOGÍA"]
    assert {f["categoria"] for f in bact} == {"Ausencia", "Presencia", "<1"}
    assert all(f["valor"] is None and f["condicion"] == "categoria" for f in bact)


def test_el_menor_que_uno_de_bacteriologia_no_rompe_el_archivo(tmp_path):
    # Son 2 filas en 152.967, las dos de Laguna del Cisne y las dos de 2020. Un dominio de dos
    # valores rechazaría el archivo entero por ellas; se declaran y se cuentan.
    r = ose.resumen(ose.leer(_escribir(tmp_path / "ose.csv")))
    assert r["categorias"]["<1"] == 1


def test_una_categoria_nueva_se_rechaza(tmp_path):
    p = _escribir(tmp_path / "ose.csv", [FILAS[5].replace('"Ausencia"', '"Ausente"')])
    with pytest.raises(OseInvalido, match="COLIFORMES TOTALES"):
        ose.leer(p)


def test_un_parametro_desconocido_se_rechaza(tmp_path):
    p = _escribir(tmp_path / "ose.csv", [FILAS[0].replace('"PH"', '"CLORO LIBRE"')])
    with pytest.raises(OseInvalido, match="parámetro desconocido"):
        ose.leer(p)


def test_el_trimestre_es_un_intervalo_no_un_dia(tmp_path):
    # El archivo no trae la fecha de la muestra: lo más fino que se puede afirmar es el trimestre.
    filas = {(f["anio"], f["trimestre"]): f for f in ose.leer(_escribir(tmp_path / "ose.csv"))}
    assert (filas[(2025, 1)]["desde"], filas[(2025, 1)]["hasta"]) == (date(2025, 1, 1), date(2025, 3, 31))
    assert (filas[(2025, 2)]["desde"], filas[(2025, 2)]["hasta"]) == (date(2025, 4, 1), date(2025, 6, 30))
    assert (filas[(2025, 3)]["desde"], filas[(2025, 3)]["hasta"]) == (date(2025, 7, 1), date(2025, 9, 30))
    assert (filas[(2025, 4)]["desde"], filas[(2025, 4)]["hasta"]) == (date(2025, 10, 1), date(2025, 12, 31))


def test_un_trimestre_ilegible_se_rechaza(tmp_path):
    p = _escribir(tmp_path / "ose.csv", [FILAS[0].replace('"trimestre 1"', '"1"')])
    with pytest.raises(OseInvalido, match="trimestre ilegible"):
        ose.leer(p)


def test_una_columna_de_mas_se_rechaza(tmp_path):
    p = tmp_path / "ose.csv"
    p.write_text(ENCABEZADO + ";EXTRA\n" + FILAS[0] + ';"x"\n', encoding="utf-8")
    with pytest.raises(OseInvalido, match="columnas inesperadas"):
        ose.leer(p)


def test_una_muestra_puede_tener_mas_de_un_laboratorio(tmp_path):
    # 1.773 muestras de bacteriología y 3.161 de fisicoquímico están en más de un laboratorio:
    # contar filas sobrecuenta muestras.
    r = ose.resumen(ose.leer(_escribir(tmp_path / "ose.csv")))
    assert r["filas"] == 8
    assert r["muestras"] == 5
    assert r["muestras_con_mas_de_un_laboratorio"] == 1


def test_el_resumen_declara_los_extremos_en_vez_de_rechazarlos(tmp_path):
    # Así se ve el pH de 251,0 (una fila en 133.287) sin rechazar el archivo entero.
    p = _escribir(tmp_path / "ose.csv", [FILAS[0].replace('"6,8"', '"251,0"'), FILAS[1]])
    e = ose.resumen(ose.leer(p))["extremos"]["PH"]
    assert (e["min"], e["max"], e["n"]) == (6.9, 251.0, 2)


def test_filtrar_por_localidad_que_no_esta_se_rechaza(tmp_path):
    # Un filtro que no devuelve nada casi siempre es un nombre mal escrito, no una localidad vacía.
    with pytest.raises(OseInvalido, match="Treinta y Tres"):
        ose.leer(_escribir(tmp_path / "ose.csv"), localidades=["Treinta y Tres"])


def test_el_recurso_se_elige_por_el_nombre_del_archivo_no_por_el_del_recurso(monkeypatch):
    # El nombre del recurso lleva el rango de fechas adentro, así que cambia cada año. Y el archivo
    # de metadatos contiene los dos nombres: hay que comparar por prefijo, no por subcadena.
    monkeypatch.setattr(
        catalogo,
        "accion",
        lambda nombre, **kw: {
            "resources": [
                {
                    "id": "r0",
                    "name": "Metadatos análisis laboratorio",
                    "url": "https://x/metadatos_calidad_agua_bacteriologia_y_fisicoquimico.csv",
                    "size": 699,
                },
                {
                    "id": "r1",
                    "name": "Bacteriología desde 2017-Trimestre 1 a 2026-Trimestre 2",
                    "url": "https://x/calidad_de_agua_bacteriologia_2017t1_2026t2.csv",
                    "size": 31259384,
                },
                {
                    "id": "r2",
                    "name": "Fisicoquímico desde 2017-Trimestre 1 a 2026-Trimestre 2",
                    "url": "https://x/calidad_de_agua_fisicoquimico_2017t1_2026t2.csv",
                    "size": 96317443,
                },
            ]
        },
    )
    r = ose.recursos_vigentes()
    assert set(r) == {"bacteriologia", "fisicoquimico"}
    assert r["bacteriologia"]["recurso"] == "r1"
    assert r["fisicoquimico"]["recurso"] == "r2"


def test_si_falta_un_csv_se_rechaza_nombrando_lo_que_llego(monkeypatch):
    monkeypatch.setattr(
        catalogo,
        "accion",
        lambda nombre, **kw: {"resources": [{"id": "r0", "url": "https://x/otra_cosa.csv", "size": 1}]},
    )
    with pytest.raises(OseInvalido, match="otra_cosa.csv"):
        ose.recursos_vigentes()


def test_no_se_baja_un_archivo_que_ya_esta_completo(tmp_path):
    p = tmp_path / "bacteriologia.csv"
    p.write_bytes(b"x" * 100)
    assert ose.hace_falta_bajar("bacteriologia", p, {"bytes": 100, "modificado": "2026-06-29"})[0] is False
    assert ose.hace_falta_bajar("bacteriologia", p, {"bytes": 101, "modificado": "2026-06-29"})[0] is True
    assert ose.hace_falta_bajar("bacteriologia", tmp_path / "no.csv", {"bytes": 100, "modificado": ""})[0] is True
    # Sin tamaño declarado no se puede decidir: se baja.
    assert ose.hace_falta_bajar("bacteriologia", p, {"bytes": None, "modificado": ""})[0] is True


def test_dos_lecturas_que_no_coinciden_se_rechazan(monkeypatch):
    # El CSV y el datastore son dos lecturas independientes de la misma fuente: si no coinciden,
    # la fuente se movió o el archivo del disco quedó viejo.
    monkeypatch.setattr(ose, "recursos_vigentes", lambda: {"bacteriologia": {"recurso": "r1"}})
    monkeypatch.setattr(catalogo, "datastore_search", lambda *a, **kw: {"total": 8776, "campos": [], "filas": []})
    filas = [{"localidad": "Salto"}] * 8776
    assert ose.verificar_contra_datastore("bacteriologia", "Salto", filas)["filas"] == 8776
    with pytest.raises(OseInvalido, match="8775 filas y el datastore declara 8776"):
        ose.verificar_contra_datastore("bacteriologia", "Salto", filas[:-1])


@pytest.mark.red
def test_el_dataset_real_declara_los_dos_csv():
    """Medido el 2026-10-25: el dataset `calidad-de-agua` del CKAN de OSE trae los dos CSV de datos
    más el de metadatos. Si los nombres de archivo cambian de prefijo, esto falla y hay que volver
    a medir."""
    r = ose.recursos_vigentes()
    assert set(r) == {"bacteriologia", "fisicoquimico"}
    assert r["bacteriologia"]["archivo"].startswith("calidad_de_agua_bacteriologia")
    assert r["fisicoquimico"]["archivo"].startswith("calidad_de_agua_fisicoquimico")
    assert r["bacteriologia"]["recurso"] and r["fisicoquimico"]["recurso"]


@pytest.mark.red
def test_el_datastore_real_filtra_con_texto_y_no_con_entero():
    """La trampa medida el 2026-10-25: los campos están tipados `text` incluso para el año.
    `{"ANIO": 2025}` con un entero devuelve HTTP 409; `"2025"` anda. Y `LOCALIDAD=Salto` da 8.776
    filas de las 152.967 del recurso de bacteriología."""
    recurso = ose.recursos_vigentes()["bacteriologia"]["recurso"]
    con_texto = catalogo.datastore_search(recurso, base=ose.ACCIONES, limite=1, filtros={"ANIO": "2025"})
    assert con_texto["total"] > 0
    assert catalogo.datastore_search(recurso, base=ose.ACCIONES, limite=0)["total"] == 152967
    with pytest.raises(OSError, match="409"):
        catalogo.datastore_search(recurso, base=ose.ACCIONES, limite=1, filtros={"ANIO": 2025})


@pytest.mark.red
def test_los_archivos_reales(tmp_path):
    """Los dos CSV completos: **122 MB de descarga**, por eso sólo con `-m red`. Los números son los
    medidos el 2026-10-25 y están en el docstring del módulo. Si cambian, la fuente publicó el
    trimestre siguiente: se vuelve a medir y se actualiza el docstring, no el test."""
    from uydatos.procedencia import sha256

    rutas = ose.descargar(tmp_path)
    assert sha256(rutas["bacteriologia"]) == "0855acc69f06ca17a58f4e60a95bbeb357abaf49b46470d1ebea3c83ecc12709"
    assert sha256(rutas["fisicoquimico"]) == "ae052ae069d70bfec21348b6f36005436d1ba4448c4fad8885f36943a55b8781"

    b = ose.resumen(ose.leer(rutas["bacteriologia"]))
    assert (b["filas"], b["muestras"], b["muestras_con_mas_de_un_laboratorio"]) == (152967, 76784, 1773)
    assert b["categorias"] == {"Ausencia": 151980, "Presencia": 985, "<1": 2}
    assert (b["localidades"], b["trimestres"]) == (38, 36)

    q = ose.resumen(ose.leer(rutas["fisicoquimico"]))
    assert (q["filas"], q["muestras"], q["muestras_con_mas_de_un_laboratorio"]) == (531679, 133598, 3161)
    assert (q["localidades"], q["trimestres"]) == (41, 36)
    assert (q["censurados"], q["censurados_al_reves"]) == (142212, 4)
    assert (q["con_punto_decimal"], q["con_coma_decimal"]) == (50649, 348513)
    assert q["extremos"]["PH"]["max"] == 251.0, "el pH imposible de Melo 2017-T2 sigue ahí"
    # Las dos localidades que no están en los dos archivos: cruzarlos por localidad no cierra.
    assert q["localidades"] != b["localidades"]
