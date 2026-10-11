"""Pruebas contra las fuentes reales. **Salen a internet**: no corren por defecto.

    pytest -m red

Sirven para enterarse de que una fuente cambió de forma (otra URL, otro formato, otra moneda),
no para validar la lógica: eso lo hacen los demás tests, sin red.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import pytest

from uydatos import (
    ancap,
    ancap_ventas,
    bcu,
    catalogo,
    compras,
    elecciones,
    hojas,
    ibge,
    ideuy,
    indec,
    inumet,
    limites,
    mides,
    observatorio,
    parlamento,
    red,
    salto_grande,
    ursea,
)
from uydatos.catalogo import recursos

pytestmark = pytest.mark.red


def test_bcu_dolar_de_un_mes_cerrado(tmp_path):
    (p,) = bcu.descargar(2225, "2026-01", "2026-01", tmp_path)
    serie = bcu.leer_crudo(p, 2225)
    assert 15 <= len(serie) <= 23
    assert all(30 < v < 60 for v in serie.values())


def test_indec_serie_viva(tmp_path):
    serie = indec.leer(indec.descargar(tmp_path / "ipc.json"))
    assert serie[0] == {"periodo": "2016-12", "valor": pytest.approx(100.0)}


def test_ibge_ipca(tmp_path):
    serie = ibge.leer(ibge.descargar(tmp_path / "ipca.json"))
    assert next(s["valor"] for s in serie if s["periodo"] == "1993-12") == 100


def test_salto_grande_lista(tmp_path):
    estaciones = salto_grande.leer_estaciones(salto_grande.descargar_lista(tmp_path / "e.xml"))
    assert len(estaciones) > 10


def test_ancap_csv(tmp_path):
    serie = ancap.serie_mensual(ancap.leer_publicaciones(ancap.descargar(tmp_path / "a.csv")))
    assert any(s["precio"] for s in serie)


def test_catalogo_inia_tiene_csv_anuales():
    assert any("ppt_tmax_tmin_sg_" in r["url"] for r in recursos("inia-precipitacion-temps-extremas-sg"))


def test_inumet_los_seis_datasets_declaran_un_solo_csv():
    """Si un dataset cambia de nombre, o sube un segundo archivo de datos, `descargar()` deja de
    poder elegir cuál es el bueno: mejor enterarse acá y no en la corrida de alguien."""
    for nombre, (dataset, _, _) in inumet.DATASETS.items():
        nombres = [Path(r["url"].split("?")[0]).name for r in recursos(dataset)]
        # El catálogo publica el mismo dato en CSV, XML y XLSX (medido el 10/10/2026): lo que tiene que
        # ser único es el CSV, que es el que elige `descargar()` con el mismo patrón.
        assert len([n for n in nombres if inumet._ARCHIVO.match(n)]) == 1, f"{nombre}: {nombres}"


def test_inumet_temperatura_contrato(tmp_path):
    """El archivo completo de temperatura, con su trampa adentro.

    Medido el 09/10/26: 332.070 valores y **una fila cuyo `estacion_id` es el texto de un error
    del servidor**. Si el lector empieza a devolver una octava estación, la fuente cambió: hay
    que mirarla antes de creerle.
    """
    ruta = inumet.descargar("temperatura", tmp_path / "inumet_temperatura.csv")
    serie = inumet.leer_archivo(ruta, inumet.DATASETS["temperatura"][1])
    assert len(serie) > 300_000
    assert {f["estacion"] for f in serie} <= set(inumet.ESTACIONES)
    assert serie[0]["fecha"] < serie[-1]["fecha"]


def test_ideuy_edificio_publico_calle_inexistente_y_esquina():
    import time

    from uydatos import ideuy

    r = ideuy.geocodificar("Avenida 18 de Julio 1360", "Montevideo", "Montevideo")  # Intendencia de Montevideo
    assert r["calidad"] == "puerta_exacta" and r["dentro_de_uruguay"]
    time.sleep(1)
    assert ideuy.geocodificar("Calle que no existe 123", "Montevideo", "Montevideo")["calidad"] == "calle_distinta"
    time.sleep(1)
    assert ideuy.geocodificar("18 de Julio y Ejido", "Montevideo", "Montevideo")["calidad"] in (
        "esquina",
        "calle_sin_numero",
    )


@pytest.mark.red
def test_buscar_por_organizacion_mides():
    """Medido el 2026-10-09: 1.875. Se afirma un piso y no el número exacto: un dataset nuevo del MIDES
    no es un error, y un test semanal que falla por eso enseña a ignorarlo."""
    assert catalogo.buscar("", organizacion="mides")["total"] >= 1500


@pytest.mark.red
def test_el_datastore_de_inumet_se_puede_consultar_sin_bajar_el_archivo():
    """Medido el 2026-10-09: `total` 332.071 e incluye la fila del encabezado."""
    r = catalogo.datastore_search("f800fc53-556b-4d1c-8bd6-28b41f9cf146", limite=2)
    assert r["total"] == 332071
    assert "temp_aire" in r["campos"]


def test_la_familia_de_mides_son_indicadores():
    """Medido el 2026-10-09: la organizacion declara 1.875 datasets y 1.869 son de la familia. Se afirma
    un piso: un indicador nuevo no es un error."""
    r = mides.indicadores(filas=100)
    assert r["total"] >= 1500
    assert all(d["nombre"].startswith("mides-indicador-") for d in r["indicadores"])


def test_un_indicador_de_mides_se_baja_y_se_lee(tmp_path):
    """Medido el 2026-10-09: el 10745 tiene dos filas y sus columnas son `año, valor`."""
    ruta = mides.descargar("10745", tmp_path / "mides-10745.csv")
    s = mides.resumen(ruta)
    assert s["columnas"] == ["año", "valor"]
    assert s["filas"] == 2
    assert s["filas_en_blanco"] == 0


def test_salto_grande_lecturas_de_la_estacion_salto(tmp_path):
    from datetime import date

    ruta = salto_grande.descargar_datos("A501258E", date(2026, 9, 1), date(2026, 9, 2), tmp_path / "s.xml")
    lecturas = salto_grande.leer_datos(ruta)
    assert 90 <= len(lecturas) <= 97
    assert all(f["H"] is not None and 0 < f["H"] < 20 for f in lecturas)


def test_limites_departamentos_y_localidades(tmp_path):
    deps = limites.leer("departamentos", limites.descargar("departamentos", tmp_path / "d.geojson"))
    assert sum(1 for a in deps if a["tipo"] == "departamento") == 19
    assert limites.ubicar(deps, -31.3833, -57.9606)["nombre"] == "SALTO"
    locs = limites.leer("localidades", limites.descargar("localidades", tmp_path / "l.geojson"))
    salto = limites.ubicar(locs, -31.3833, -57.9606)
    assert salto["nombre"] == "SALTO" and salto["datos"]["poblacion_2023"] > 100_000


def test_inversa_ordena_por_distancia():
    r = ideuy.inversa(-31.3833, -57.9606, 3)
    assert len(r) <= 3 and r[0]["distancia_km"] < 0.5 and r[0]["departamento"] == "SALTO"


def test_buscar_geojson_no_da_cero():
    assert catalogo.buscar("", formato="geojson", filas=1)["total"] > 0


def test_balotaje_2024_mesas_comunes_y_de_observados(tmp_path):
    mesas = elecciones.leer_totales(elecciones.descargar("balotaje-2024", "totales", tmp_path / "b.csv"))
    r = elecciones.resumen(mesas)
    assert r["mesas_comunes"] > 7000 and r["mesas_de_observados"] > 100
    assert r["en_mesas_comunes_las_opciones_excluyen_observados"]


def test_hojas_el_unico_xls_de_verdad_de_la_muestra(tmp_path):
    """Medido el 10/10/26: de 24 recursos declarados `XLS`, el único que es un OLE de verdad es el de
    AGESIC. La firma lo dice sin abrir ninguna biblioteca."""
    recurso = [r for r in recursos("agesic-encuestas-de-uso-de-tic") if (r["formato"] or "").upper() == "XLS"][0]
    destino = tmp_path / "eutic.xls"
    red.bajar(recurso["url"], destino)
    assert hojas.firma(destino) == "xls"
    assert len(hojas.leer(destino)) > 10


def test_hojas_un_recurso_declarado_xls_que_en_realidad_es_xlsx(tmp_path):
    """Es la trampa medida: el catálogo declara `XLS` y el archivo es un XLSX. Quien eligiera el motor
    por el metadato —o por la extensión— se cae; por firma no, y este test lo fija."""
    recurso = [r for r in recursos("latu-capital_humano_latu") if (r["formato"] or "").upper() == "XLS"][0]
    destino = tmp_path / "latu.xls"
    red.bajar(recurso["url"], destino)
    assert hojas.firma(destino) == "xlsx"
    assert hojas.leer(destino)


def test_hojas_el_xlsx_de_un_indicador_de_mides(tmp_path):
    """Medido el 10/10/26: trae la hoja `Datos` —la misma tabla que su CSV, con los números ya
    tipados— y una hoja `Metadatos` que declara el tipo de cada columna."""
    recurso = [r for r in recursos("mides-indicador-13198") if (r["formato"] or "").upper() == "XLSX"][0]
    destino = tmp_path / "mides-13198.xlsx"
    red.bajar(recurso["url"], destino)
    assert hojas.nombres(destino) == ["Datos", "Metadatos"]
    datos = hojas.leer(destino, "Datos")
    assert datos[0] == ["Funciones GPS_fg", "año", "valor"]
    assert isinstance(datos[1][2], (int, float)), "los números vienen tipados, no como texto"
    assert hojas.leer(destino, "Metadatos")[0] == ["nombreDeAtributo", "descripcion", "tipoDeDato"]


def test_compras_2025_se_lee_y_muestra_su_concentracion(tmp_path):
    adjs = compras.leer_adjudicaciones(compras.descargar(2025, tmp_path / "c.zip"))
    s = compras.resumen(adjs)
    assert s["adjudicaciones"] > 100_000 and "UYU" in s["importes"]
    assert s["mayores_items"] and s["concentracion_uyu"]["mayor_item_pct"] > 0


def test_parlamento_senado_actual_y_leyes(tmp_path):
    asis = parlamento.leer_asistencias(parlamento.descargar("asistencias-senado", tmp_path / "s.csv", 50))
    assert len(asis) > 31
    leyes = parlamento.leer_leyes(parlamento.descargar("leyes", tmp_path / "l.csv"))
    assert len(leyes["leyes"]) > 4700 and leyes["faltantes"] == []


def test_los_recursos_de_la_ech_no_bajan_un_archivo():
    """La ECH del INE: el catálogo la declara, los enlaces no entregan un archivo.

    Medido el 10/10/26: sus siete datasets (`ine-ech2011` y `ine-encuesta-continua-de-hogares-*`)
    declaran 25 recursos contra `www.ine.gub.uy`, y **los 25 devuelven la portada del sitio nuevo**
    (HTML, con el `uuid` conservado como consulta). El host está vivo: no es un certificado roto ni un
    enlace lento, es link rot, y el `formato` declarado miente.

    Se prueba **uno** de los 25 como canario —son la misma URL contra el mismo host—, porque este host
    deja colgado el pedido cuando no responde y pedir los 25 cuesta siete minutos. El día que alguno
    vuelva a entregar un archivo, este test falla: es la señal para escribir el lector.
    Ver `docs/2026-10-09-fuentes-candidatas.md`, sección 4.
    """
    firma_de_archivo = (b"Rar!", b"\xd0\xcf\x11\xe0", b"PK\x03\x04", b"%PDF")
    datasets = {
        d["nombre"]
        for consulta in ("encuesta continua de hogares", "ech")
        for d in catalogo.buscar(consulta, filas=50)["datasets"]
        if "encuesta-continua" in d["nombre"] or d["nombre"].startswith("ine-ech")
    }
    assert len(datasets) >= 5, "el catálogo dejó de listar la ECH: revisar antes de tocar la guarda"

    hosts = set()
    for nombre in sorted(datasets):
        try:
            hosts |= {urlparse(r["url"]).netloc for r in recursos(nombre)}
        except Exception:  # noqa: BLE001,S110 - un dataset sin recursos no dice nada de los enlaces
            continue

    primero = recursos("ine-ech2011")[0]
    try:
        # Un pedido chico alcanza para mirar la firma del archivo, sin bajar el archivo entero.
        cuerpo = red.pedir(primero["url"], cabeceras={"Range": "bytes=0-999"}, timeout=10)
    except OSError:
        # El TLS de este host se corta a veces (cadena incompleta): tampoco entrega un archivo.
        cuerpo = b""

    entrego_archivo = cuerpo.startswith(firma_de_archivo)
    assert not entrego_archivo, (
        f"la fuente mejoró: la ECH volvió a entregar un archivo ({primero['formato']}). "
        "Escribir el lector, ver docs/2026-10-09-fuentes-candidatas.md, sección 4"
    )
    assert hosts == {"www.ine.gub.uy"}, (
        f"el catálogo movió los archivos de la ECH a otro host: {sorted(hosts)}. "
        "Si es su propio host, la ECH es alcanzable: escribir el lector"
    )


def test_ancap_ventas_el_csv_del_catalogo(tmp_path):
    """Medido el 10/10/26: 1.200 filas, las dos unidades, y el mercado INTERNO es el 81% de los m³.

    `Toneladas` son sólo los combustibles sólidos del mercado interno, así que sigue habiendo dos
    unidades: el día que sea una sola, este test lo dice (y el resumen cambia de forma).
    """
    r = ancap_ventas.resumen(ancap_ventas.leer(ancap_ventas.descargar(tmp_path / "v.csv")))
    assert r["filas"] > 1000
    assert set(r["unidades"]) == {"Miles de m3", "Toneladas"}
    por_mercado = {m: u.get("Miles de m3", 0) for m, u in r["por_mercado"].items()}
    assert max(por_mercado, key=por_mercado.get) == "INTERNO"
    assert any(c["faltan"] for c in r["cobertura"].values()), "la ventana móvil dejó un año completo"


def test_observatorio_el_sitemap_y_una_pagina_viva():
    """Medido el 11/10/26: 1.264 indicadores en el sitemap; la tasa de actividad por sexo llega a 2024.

    La copia del catálogo (`uydatos.mides`) quedó en 2019: si esta página deja de pasar de 2019, el
    motivo de este módulo desapareció y hay que volver a mirar.
    """
    slugs = observatorio.indice()
    assert len(slugs) > 1000
    assert "tasa-actividad-segun-sexo-total-pais" in slugs
    r = observatorio.leer("tasa-actividad-segun-sexo-total-pais")
    assert r["dimensiones"] == ["Sexo"] and r["unidad"]
    assert max(int(p) for p in r["periodos"]) >= 2024


def test_ursea_ppi_y_ancap_ex_planta(tmp_path):
    """Medido el 11/10/26: 57 ventanas de PPI (una imposible, descartada), y la comparación de la
    Súper 95 cubre 55 meses desde 2022-01. Si aparece un conflicto en las gasolinas o los gasoils, o
    se corrige la ventana imposible, este test lo dice."""
    archivos = ursea.descargar(tmp_path)
    ppi = ursea.leer_ppi(archivos["ppi"])
    ex = ursea.leer_ex_planta(archivos["ex_planta"])
    assert len(ppi["descartadas"]) == 1
    assert not [c for c in ex["conflictos"] if c["producto"] in ursea.COMPARABLES]
    assert len(ursea.comparar(ppi, ex, "Gasolina Super 95")) >= 55
    assert len(ursea.leer_componentes(archivos["componentes"])) >= 355
