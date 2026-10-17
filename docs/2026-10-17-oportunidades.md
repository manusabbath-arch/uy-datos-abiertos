# Qué se toma de afuera, y qué datos de Uruguay quedan por leer

Fecha: 2026-10-17 (hora de Montevideo). Cada cifra de acá sale de un comando que está escrito al
lado, o de un archivo con su sha256. Nada está re-tipeado de memoria.

## 1. Método

Una oportunidad entra si (a) un proyecto o una medición externa muestra que el problema existe, y
(b) se puede cerrar con una guarda o un lector verificable. Lo que no cumple (b) queda como
candidata con su gate escrito, y lo que se descarta queda con su motivo medido.

El paquete no cambia de forma por esto: bajar sigue separado de leer, cada fuente sigue con su
excepción y sus trampas en el docstring, y los tests siguen separados entre fixture (cada commit) y
fuente real (`-m red`, semanal).

## 2. Las cinco referencias, y qué se toma de cada una

| Referencia | Qué hace | Qué se toma | Qué se rechaza |
|---|---|---|---|
| [DBnomics](https://docs.db.nomics.world/) (`dbnomics-toolbox`) | Agrega series de decenas de proveedores con un modelo común | guardar el original tal cual, separar bajar de convertir, **conservar las revisiones** y evitar las falsas, un fetcher por proveedor | su modelo provider → dataset → series → observación: acá cada lector ya es un proveedor, y el paquete no agrega series |
| [API de series de tiempo de Argentina](https://datosgobar.github.io/series-tiempo-ar-api/) | `representation_mode`, `collapse`, `metadata=only` | las transformaciones son una **capa declarada y nombrada**, no algo que cada consumidor inventa | la normalización de períodos y el `collapse` como parámetro: los lectores ya devuelven `date` |
| [Frictionless Data](https://specs.frictionlessdata.io/) (Data Package, Table Schema, Table Dialect) | Contrato declarativo por recurso: columnas, tipos, constraints, dialecto | el contrato se declara y se puede emitir desde la tabla de columnas que cada módulo ya tiene | la dependencia `frictionless` y el `datapackage.json` como formato de salida: nadie lo pidió |
| [Análisis de mutación](https://www.fuzzingbook.org/html/MutationAnalysis.html), cap. del *Fuzzing Book*; [`mutmut`](https://mutmut.readthedocs.io/) | Mide si la suite detecta un defecto inyectado | mutar para medir la suite — acá se mutan **los datos**, no el código | `mutmut`: pide `fork`, y esta máquina no tiene WSL |
| [Link rot](https://www.pewresearch.org/data-labs/2024/05/17/when-online-content-disappears/) (Pew Research, 2024: 21% de las páginas de gobierno tienen algún enlace roto) | Mide la desaparición de lo publicado | el caso ECH (25 de 25 enlaces muertos) no es una rareza local; el chequeo de vida tiene que ser periódico y barato | sus conclusiones sobre portales que acá no se midieron |

## 3. Lo medido hoy en Uruguay

### 3.1 El catálogo no cuenta lo mismo por sus dos endpoints

```sh
uv run --quiet python -c "from uydatos import catalogo; print(len(catalogo.accion('package_list'))); print(catalogo.accion('package_search', q='*:*', rows=0)['count'])"
```

| Endpoint | Datasets |
|---|---|
| `package_list` | **2.777** |
| `package_search q=*:*` | **2.716** |
| diferencia | **61 (2,2%)** |

Dos cosas que se siguen de ahí, y que cambian una regla escrita: el **buscador no ve el catálogo
entero**, y el total **bajó** desde los 2.779 del 2026-10-09. Un conteo de una fuente viva no es un
piso: es una foto con fecha, y las dos fotos se sacan por endpoints distintos.

El catálogo tiene **73 organizaciones**.

### 3.2 El INE publica poco en el catálogo, y el IPC no está

Los 15 datasets de `organization:ine` son: 7 de la Encuesta Continua de Hogares 2011–2017 (los
mismos cuyos 25 recursos devuelven la portada del sitio nuevo), 4 institucionales (autoridades,
datos de contacto, marco jurídico, organigrama), la EUTIC, y tres de remuneraciones y presupuesto.
**Ninguno es el Índice de Precios del Consumo.**

El único dataset del catálogo que se titula «Índice de Precios al Consumo (IPC)» es
`mides-indicador-10449`, del MIDES, con `metadata_modified` del 2020-01-22. Los otros tres
resultados de buscar `ipc` son indicadores del MIDES que lo mencionan en el título.

O sea: la estadística que el país publica todos los meses no entra por el catálogo. La inflación
que el paquete ya puede leer entra por otro lado, la Unidad Indexada del BCU (`bcu.a_pesos_de`).

### 3.3 La OPP: 19 datasets, casi todos CSV, y hay que medir si están vivos

| dataset | recursos | `metadata_modified` |
|---|---|---|
| `opp-credito-presupuestal-detallado-a-partir-de-2011` | 13 CSV + 1 XLS | 2022-07-11 |
| `opp-historico-de-credito-presupuestal-ejecutado` | 4 CSV + 1 PDF | 2020-12-15 |
| `opp-historico-de-credito-y-ejecucion-presupuestal-por-ue` | 1 CSV + 1 PDF | 2020-12-15 |
| `opp-ingresos-y-egresos-de-los-gobiernos-departamentales-...` | 3 CSV + 3 JSON + 3 XML + 3 XLSX + 2 PDF | 2024-08-29 |

Son el bloque de datos presupuestales más grande que el paquete no lee, y el formato no es el
problema. Lo que hay que medir antes es si están congelados como la copia de MIDES, y las columnas
no coinciden entre datasets: es un lector por dataset, no uno por organismo.

### 3.4 El SIPC creció, y el gate sigue vivo

Recurso de precios por año, del catálogo: 2022 = 1.596.244.928 bytes; 2024 = 1.713.538.504;
2025 = 2.024.669.561; y ya hay un **2026 parcial de 1.004.151.618** (modificado el 2026-07-17).
Se mantiene la regla escrita: no se lee hasta que exista una pregunta que necesite más de un año.

### 3.5 Las sanciones del DSS: la fecha se mueve y el archivo no

| Qué | Valor |
|---|---|
| dataset | `defensa-del-consumidor-sanciones-a-empresas` |
| `metadata_modified` | 2026-03-22 |
| archivo | 168.759 bytes, sha256 `241a78a15e951bf960f93efc12aebe0d04dc343b24198a2fa4899d1872dd4cd0` |
| el mismo sha el 2026-10-09 | **sí** |

El catálogo declara el archivo modificado en marzo y el archivo es el mismo, byte a byte, que el
que se midió el 2026-10-09. Al revés también pasa: ANCAP republicó el 2026-10-12 y cambió el id del
recurso. Conclusión para el paquete: **una fecha del catálogo no es una revisión**. Avisa que hay
que mirar; lo que dice si el dato cambió es comparar dos copias.

## 4. Lo que se rechaza, con el motivo

| Candidata | Por qué no |
|---|---|
| Lector del IPC del INE | §3.2: no está en el catálogo, y la inflación ya entra por la UI. Gate: una pregunta que la UI no conteste (IPC por rubro). |
| Un lector por cada dataset de la OPP | §3.3: columnas distintas y fechas de 2020/2022. Entra después del mapa, con la medición de si están congelados adelante. |
| SIPC: la serie de precios | §3.4: 1 a 2 GB por año. El gate sigue siendo «una pregunta que necesite más de un año». |
| `pandera`, `great_expectations`, `frictionless` como dependencia | El paquete base no tiene dependencias y ese es el contrato del README. Falta la guarda, no el framework. |
| `mutmut` en el CI | Pide `fork`: esta máquina no tiene WSL. Se mutan los datos. |
| `datapackage.json` por lector | Un formato de salida que nadie pidió. Si hiciera falta, sale de la tabla de columnas de cada módulo. |
| Traducir los docstrings al inglés | Duplica el mantenimiento de lo único que el paquete vende: las trampas medidas. |

## 5. Prioridad

| # | Oportunidad | Qué desbloquea | Costo |
|---|---|---|---|
| 1 | El mapa del catálogo (`catalogo.formatos`, `faltantes`) | ordena todo lo que se escriba después con números | bajo |
| 2 | El arnés de trampas (`tests/test_trampas.py`) | la tesis del paquete pasa a ser una guarda, en las dos direcciones | bajo |
| 3 | El manifiesto de fuentes (`uydatos.fuentes`) | separa «la fuente se movió» de «la corrida falló» | medio |
| 4 | Revisiones (`uydatos.revisiones`) | dice **qué** cambió entre dos copias | bajo |
| 5 | El lector de sanciones del DSS (`uydatos.sanciones`) | una fuente medida dos veces, con el límite de PII declarado | medio |

El detalle de cada una, con los tests y los comandos, está en el plan de la sesión
(`.hermes/plans/`, que no se versiona: cita rutas de máquina).
