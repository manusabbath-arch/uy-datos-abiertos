# El mapa del catálogo de datos abiertos

Fecha: 2026-10-17 (hora de Montevideo). Todo lo de acá sale de `uydatos.catalogo` tal como quedó en
la versión 0.13.0, y se puede volver a medir con los comandos que están en cada sección.

## 1. Los dos endpoints no cuentan lo mismo

```sh
uv run --quiet python -m uydatos.catalogo --faltantes
```

| Qué | Cuántos |
|---|---|
| `package_list` (el endpoint de la lista) | **2.777** |
| `package_search q=*:*` (el buscador) | **2.716** |
| diferencia | **61** |

El 2026-10-09 la lista traía 2.779. O sea: el total **bajó**, y un test que lo afirme como piso
también envejece.

### Qué son los 61

Los 61 existen, están `state=active` y tienen **cero recursos**. No son datasets borrados: son
fichas sin archivo —visualizadores, apps, servicios— que el catálogo cuenta como dataset y el
buscador no indexa. Medido uno por uno con `package_show`:

| Estado | Cuántos |
|---|---|
| `state=active`, 0 recursos | **61** |
| con organización en la respuesta | 2 de 61 (uno de `intendencia-montevideo`, uno de `ose`) |

Ejemplos que se leen solos: `app-coronavirus-uy-app-store`, `dondereciclo`, `montevideo-en-bici`,
`nomenclator-de-calles`, `monitor-de-compras-publicas`, `preciosgub`,
`web-service-de-actualizaciones-al-catalogo`, y nueve `visualizador-*`.

La lista completa:

```
a-donde-van-nuestros-impuestos · a-tu-nombre · a-tu-servicio ·
anuario-estadistico-del-poder-judicial · app-a-tu-nombre-udelar ·
app-coronavirus-uy-app-store · app-coronavirus-uy-google-play ·
buscador-de-obras-del-acervo · como-ir · con-la-tuya-contribuyente ·
contenedores-para-depositar-material-reciclable · covid-19-vacunas-uy ·
derechos-de-estudiantes · dondereciclo · elecciones-en-datos · elijo-estudiar ·
gastos-por-actos-medicos · gestion-administrativa-digital ·
imputaciones-y-condenas-a-personas ·
indicadores-de-gestion-de-los-canales-de-atencion-a-la-ciudadania ·
indicadores-de-la-declaracion-jurada-dicose-snig-2016 ·
indicadores-de-la-declaracion-jurada-dicose-snig-2017 ·
indicadores-de-la-declaracion-jurada-dicose-snig-2018 ·
indicadores-de-la-declaracion-jurada-dicose-snig-2019 ·
indicadores-de-la-unidad-de-acceso-a-la-informacion-publica ·
informacion-de-productos-registrados · intendencia-montevideo-prod ·
interfaz-de-consulta-de-publicaciones-realizadas · monitor-de-compras-publicas ·
monitor-de-cupos-y-disponibilidades-covid-19 · montevideo-en-bici · montevideo-lbs ·
mvd-bike-montevideo-en-bicicleta · nextbus-montevideo · nomenclator-de-calles ·
observatorio-afrodescendiente · observatorio-homicidios-y-denuncias-de-otros-delitos ·
ose-prod · panel-de-indicadores-de-vinculos-con-el-estado ·
panel-de-indicadores-demograficos-de-funcionarios-del-estado · pitanga ·
planificacion-de-gobierno-en-portal-de-transparencia-presupuestaria · preciosgub ·
prestaciones-incluidas-en-el-plan-integral-de-atencion-a-la-salud-pias ·
procesamiento-paralelo-de-registros-de-accidentes-y-multas-en-la-ciudad-de-montevideo ·
red_correo · rodala · rss-de-publicaciones-realizadas ·
solicitudes-en-espera-de-agenda-por-vacunacion-covid-19 · stm-montevideo ·
visualizador-abri-cultura · visualizador-de-ambitos-de-participacion-ciudadana ·
visualizador-de-avances-de-planes-de-accion-nacional-de-gobierno-abierto ·
visualizador-de-emisiones-y-remociones-de-gases-de-efecto-invernadero ·
visualizador-de-indicadores-del-sistema-carcelario ·
visualizador-de-objetivos-y-medidas-de-mitigacion-y-adaptacion-ante-el-cambio-climatico ·
visualizador-de-violencia-domestica-y-violencia-basada-en-genero ·
visualizador-del-balance-energetico-nacional ·
visualizador-del-indice-nacional-de-transparencia-y-acceso-a-la-informacion-intai ·
visualizador-ley-n-19-973-de-promocion-de-empleo ·
web-service-de-actualizaciones-al-catalogo
```

**Consecuencia para el paquete:** la población que se puede leer es la del buscador (2.716), no la
de la lista (2.777), y de las 61 no se puede escribir un lector porque no hay archivo. Queda escrito
para que nadie las busque dos veces.

## 2. El histograma de formatos

```sh
uv run --quiet python -m uydatos.catalogo --formatos
```

El facet cuenta **datasets por formato**, no recursos: la búsqueda con `fq=res_format:CSV` devuelve
el mismo número que el facet (2.553), así que un dataset con 13 CSV cuenta una vez.

| Formato | Datasets (de 2.716) |
|---|---|
| CSV | **2.553** (94,0%) |
| JSON | 2.268 |
| XML | 2.219 |
| XLSX | 2.162 |
| TXT | 104 |
| XLS | 60 |
| SHP | 58 |
| PDF | 53 |
| GeoJSON | 21 |
| ODS / ODT | 20 / 20 |
| KML | 17 |
| ZIP | 14 |
| RAR | 10 |
| HTML | 6 |

Los números suman más que 2.716 porque un dataset puede declarar varios formatos. Y el campo
`res_format` **no está normalizado**: hay nueve formas de decir CSV (`CSV` 2.553, `csv zip` 8,
`CSV ZIP` 7, `.csv` 3, `.CSV` 1, `ZIP CSV` 1, `zip csv` 1, `CSV, XML, JSON` 1), y lo mismo pasa con
`.zip`, `Geopackage`/`geopackage`/`GPKG`, `XSD`/`xsd`. Es la misma trampa que ya está medida en
`hojas`: el formato declarado se parece a la verdad, no es la verdad.

## 3. Qué se lee hoy

`uydatos` tiene **20 lectores** (la tabla del README), sobre 2.716 datasets con al menos un CSV en el
94%. La distancia no es una deuda: cada lector entra porque cierra una pregunta y porque tiene al
menos una trampa medida. Lo que este mapa agrega es el denominador, para que esa decisión se discuta
con números y no con impresiones.

Los bloques grandes que quedan sin leer, medidos el 17/10:

| Bloque | Datasets | Formato | Qué falta antes de escribir |
|---|---|---|---|
| OPP (presupuesto, empresas públicas) | 19 | casi todos CSV; uno con 13 CSV | medir si están congelados (`metadata_modified` 2020/2022) y separar un lector por dataset |
| INE | 15 | XLS/RAR/PDF contra `www.ine.gub.uy` | los 25 enlaces de las ECH ya están medidos muertos; el resto son fichas institucionales |
| MGAP | 16 | — | medir qué trae cada uno |
| Ejecución presupuestal (búsqueda libre) | 9 | — | ídem OPP |
| SIPC (precios minoristas) | 5 (2019–2026) | CSV de 1 a 2 GB por año | el gate escrito: una pregunta que necesite más de un año |

## 4. Cómo se vuelve a medir

```sh
uv run --quiet python -m uydatos.catalogo --faltantes   # 2 peticiones + 3 páginas
uv run --quiet python -m uydatos.catalogo --formatos    # 1 petición
uv run --quiet --with pytest --with-editable . pytest -q -m red tests/test_catalogo.py
```

Una medición por vez: el catálogo devuelve `500` si se lo consulta en paralelo (medido el 17/10, con
dos sondas propias corriendo a la vez).
