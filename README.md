# uydatos

[![tests](https://github.com/manusabbath-arch/uy-datos-abiertos/actions/workflows/tests.yml/badge.svg)](https://github.com/manusabbath-arch/uy-datos-abiertos/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/uydatos)](https://pypi.org/project/uydatos/)
[![Python](https://img.shields.io/pypi/pyversions/uydatos)](https://pypi.org/project/uydatos/)
[![Licencia: MIT](https://img.shields.io/badge/licencia-MIT-blue)](LICENSE)

> **In English:** strict, dependency-free Python readers for Uruguayan and regional public data
> Central Bank of Uruguay exchange rates, ANCAP fuel prices, INIA weather in Salto, INUMET hourly
> observations from seven national stations, Uruguay River stations, Argentina's CPI, Brazil's
> IPCA, IDE.uy geocoding, RUT/ID check digits). Each reader documents its source's traps and
> **raises instead of silently fixing** bad data.

Lectores **estrictos** de datos públicos de Uruguay y la región, en Python puro (sin
dependencias).

La idea es una sola: **rechazar en vez de arreglar**. Cada fuente de acá tiene al menos una
trampa que no da error y produce una serie creíble pero falsa: una respuesta de error guardada
como si fuera un mes sin datos, columnas con los nombres invertidos, un archivo que apila
publicaciones en vez de ser una serie, una API que sigue sirviendo índices discontinuados. Cada
lector conoce las trampas de su fuente, las documenta y levanta una excepción con el motivo.

| Módulo | Fuente | Qué trae | La trampa principal |
|---|---|---|---|
| `uydatos.bcu` | Banco Central del Uruguay (web service SOAP) | Dólar, Unidad Indexada, peso argentino, real | Una respuesta de error se guarda igual y parece un mes sin cotización. |
| `uydatos.ancap` | ANCAP, catálogo de datos abiertos | Precio máximo al público de combustibles | Las columnas `Unidad` y `Valor` vienen invertidas, y el archivo apila publicaciones. |
| `uydatos.inia` | INIA, estación Salto Grande | Lluvia y temperaturas diarias desde 1970, normales y anomalías | El día va de 9:00 a 9:00; un vacío es nulo, no cero. |
| `uydatos.inumet` | INUMET, red nacional | Observaciones horarias de temperatura, lluvia, humedad, viento y presión en siete estaciones del país | La columna `estacion_id` trae el nombre y **puede traer el texto de un error del servidor**; la hora es UTC, no local. |
| `uydatos.salto_grande` | Comisión Técnica Mixta de Salto Grande (SOAP) | Estaciones hidrometeorológicas de la cuenca del río Uruguay | El arreglo SOAP encoded se llama `item`: buscar `Estacion` da lista vacía sin error. |
| `uydatos.indec` | API de series de datos.gob.ar | IPC nacional de Argentina, base dic-2016 | La API sigue sirviendo las bases 2003 y 2008, discontinuadas. |
| `uydatos.ibge` | API SIDRA del IBGE | IPCA de Brasil, número-índice | La tabla trae varias variables; una variación leída como índice no da error. |
| `uydatos.elecciones` | Corte Electoral | Resultados por mesa (totales, votos por partido, plan circuital) de las nacionales 2024, el balotaje 2024 y las departamentales 2025 | Los observados no están en cada mesa: se escrutan en **mesas especiales** sin habilitados ni localidad. Sumar todo da el definitivo; un mapa por localidad nunca cierra con el total. |
| `uydatos.limites` | INE, vía la IDE y el MIDES (WFS) | Los 19 departamentos y las 652 localidades, con población y viviendas 2023, y en cuál cae un punto | Hay 20 polígonos de departamentos: uno es el **límite contestado** con Brasil, con el código de Artigas. Sin `srsName=EPSG:4326` la capa llega en metros y ningún punto cae adentro. |
| `uydatos.ideuy` | IDE.uy (direcciones.ide.uy) | Coordenadas de una dirección o esquina, con su calidad | Ante lo que no encuentra devuelve el centro de la localidad, una puerta vecina u otra calle, sin error. |
| `uydatos.rut` | Offline | Dígito verificador de RUT y cédula | Excel convierte el RUT en float y se come el cero inicial. |
| `uydatos.semanas` | Offline | Semanas ISO 8601 (`W41`) | El 01/01/2027 es la `2026-W53`. |
| `uydatos.catalogo` | catalogodatos.gub.uy (CKAN) | URLs vigentes de los recursos de un dataset | Las URLs de descarga cambian cuando el organismo resube un archivo. |
| `uydatos.mides` | MIDES, catálogo de datos abiertos | Los 1.869 indicadores de la organización, todos con la misma forma: dimensión libre y `año, valor` al final | El CSV viene en **cp1252**, no en UTF-8: leerlo mal convierte la `ñ` en basura y no falla. |
| `uydatos.hojas` | El archivo que le des (opcional: `openpyxl` y `xlrd`) | Las filas de una hoja de cálculo XLSX o XLS, con los valores ya tipados | El `formato` que declara el catálogo miente: **23 de 24** recursos «XLS» son XLSX. El motor sale de la firma del archivo, no del metadato. |

## Instalación

```sh
pip install uydatos
```

Requiere Python 3.10 o posterior. El paquete base **no tiene dependencias**; leer planillas de
cálculo necesita el extra:

```sh
pip install "uydatos[hojas]"
```

## Uso

Cada módulo separa **bajar** (la única función que sale a internet) de **leer** (que trabaja
sobre el archivo en disco). Así lo bajado queda guardado tal cual vino, y lo que se lee se puede
volver a verificar.

```python
from pathlib import Path
from uydatos import bcu

bcu.descargar(9800, "2025-01", "2026-09", Path("datos/bcu"))   # un XML por mes
ui = bcu.leer_serie(Path("datos/bcu"), 9800)                    # {date: valor}

ui_mensual = {f["mes"]: f["promedio"] for f in bcu.promedio_mensual(ui)}
bcu.a_pesos_de({"2025-01": 1000.0}, base="2026-09", ui=ui_mensual)  # pesos constantes
```

```python
from uydatos.rut import validar_rut, validar_ci

validar_rut(12345678919.0)  # ('dv_ok_estructura_rara', '012345678919'): Excel se había comido el 0
validar_ci("1.234.567-2")    # ('valido', '12345672')
validar_ci("1.234.567-3")    # ('dv_no_valida', '12345673')
```

Desde la línea de comandos:

```sh
python -m uydatos.bcu bajar datos/bcu 2225 2026-01 2026-09
python -m uydatos.bcu serie datos/bcu 2225
python -m uydatos.ancap bajar datos/ancap.csv
python -m uydatos.ancap serie datos/ancap.csv "GASOIL 50-S *"
python -m uydatos.inia bajar datos/inia && python -m uydatos.inia resumen datos/inia
python -m uydatos.salto_grande bajar datos/estaciones.xml
python -m uydatos.salto_grande cerca datos/estaciones.xml -31.383 -57.960
python -m uydatos.indec bajar datos/ipc_ar.json
python -m uydatos.ibge bajar datos/ipca.json
python -m uydatos.catalogo inia-precipitacion-temps-extremas-sg
python -m uydatos.inumet bajar precipitacion datos/inumet_precip.csv
python -m uydatos.inumet diaria datos/inumet_precip.csv precip_horario "Salto G3" suma
python -m uydatos.ideuy "Avenida 18 de Julio 1360" --localidad Montevideo --departamento Montevideo
```

## Lo que estos lectores se niegan a hacer

- **Rellenar huecos.** Un fin de semana sin cotización devuelve `None`, salvo que se pida
  explícitamente el último día hábil (`hacia_atras=True`), y aun así no salta más de una semana.
- **Convertir un índice en inflación.** Eso es una decisión de análisis, no una lectura.
- **Inventar unidades** que la fuente no declara.
- **Elegir por vos** qué cotización corresponde a un fin fiscal.

## Tests

```sh
pip install -e ".[test]"
pytest              # sin red: todo con archivos de prueba
pytest -m red       # contra las fuentes reales
```

## Datos

Este repositorio publica **código**, no datos. Cada fuente tiene sus propias condiciones de uso;
los datos de los catálogos de Uruguay se publican bajo la Licencia de Datos Abiertos de Uruguay.

## Licencia

MIT. Usalo, adaptalo y compartilo; solo mantené el aviso de autoría.
