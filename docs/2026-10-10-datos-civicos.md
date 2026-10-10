# Datos cívicos de Uruguay: qué hay, qué muerde y por dónde empezar

Fecha: 2026-10-10. Todo lo que sigue se midió ese día sobre los archivos del catálogo de datos
abiertos (`catalogodatos.gub.uy`), bajados por HTTP. Las cifras son de esos archivos, no de
memoria. Los archivos no se versionan acá: se citan por dataset y recurso.

## 1. Por qué estos datos

Son los que más público traen: periodistas, estudiantes, investigadores, militantes de cualquier
partido y cualquier persona curiosa. Y son los que más daño hacen cuando se leen mal: un resultado
electoral mal sumado, un gasto del Estado contado dos veces o una asistencia mal calculada se
comparten igual que uno bien hecho. Por eso el criterio de este paquete —rechazar en vez de
arreglar, y declarar cada trampa— pesa más acá que en cualquier otra fuente.

## 2. Qué hay (inventario del 10/10/2026)

| Organismo | Datasets | Lo más útil | Última actualización |
|---|---|---|---|
| Corte Electoral | 14 | Resultados por mesa de todas las elecciones desde 2014, plan circuital, hojas de votación | 26/12/2025 (departamentales 2025) |
| Parlamento | 24 | Asistencias y proyectos por legislatura (desde la 42, 1985), leyes, pedidos de informes, nómina, remuneraciones por cargo | 08/09/2026 |
| ARCE (compras) | 12 | Compras del Estado 2002–2025 en **OCDS 1.1**; registro de proveedores (RUPE) mensual | 02/10/2026 |
| UAIP | 19 | Solicitudes de acceso, índice nacional de transparencia (INTAI), resoluciones | 24/07/2026 |
| OPP | 19 | Presupuesto, ingresos y egresos de los gobiernos departamentales, empresas públicas | 29/08/2024 |
| Suprema Corte | 14 | Anuarios estadísticos, nuevo proceso penal | 01/10/2026 |

Lo que **no** encontré publicado: votaciones nominales del Parlamento (figuran como candidatas en el
plan de gobierno abierto) ni diarios de sesiones legibles por máquina.

## 3. Elecciones (Corte Electoral)

### Forma

Cuatro archivos por elección, CSV en UTF-8 con BOM y coma como separador:

| Archivo | Filas (2024) | Qué trae |
|---|---|---|
| `totales-generales-por-comision-receptora-de-votos…` | 7.352 mesas | habilitados, emitidos, observados, anulados, en blanco; y en 2024 los dos plebiscitos |
| `desglose-de-votos` | 354.176 | votos por hoja (`HOJA_EN`) y por lema (`VOTO_LEMA`), por mesa |
| `plan-circuital` | 7.276 circuitos | localidad, local, tipo (urbano o rural), accesibilidad |
| `integracion-de-hojas-de-votacion` | 217.932 candidatos | nombre, sexo y **credencial cívica** de cada candidato |

La unidad es la **mesa** (comisión receptora de votos, `CRV`), con su serie. El plan circuital la
lleva a una localidad y a un local de votación, y con `uydatos.ideuy` y `uydatos.limites` se la
puede llevar al mapa y al departamento.

### Las trampas

1. **Los votos observados se cuentan en otras mesas.** En cada una de las **7.234 mesas comunes**
   —el mismo número de circuitos del escrutinio primario—, candidatos + anulados + en blanco =
   `TotalVotosNoObservados`: los observados no están. Se escrutan después en **mesas de observados**
   (118 en las nacionales 2024, 114 en el balotaje): serie terminada en `ZZ`, **0 habilitados y 0
   emitidos**, y unos 255 votos cada una. En el balotaje, las comunes declaran 35.753 observados y
   las especiales escrutan 35.539; en las nacionales, 34.587 y 34.422. La diferencia (214 y 165)
   serían observados anulados al escrutarlos, **a confirmar con la Corte**.
   - **Sumar todas las mesas da el escrutinio definitivo.**
   - **Sumar solo las comunes** —que es lo que hace cualquier mapa por circuito, por localidad o
     por local— **deja afuera los observados**, que no tienen localidad. Un mapa por barrio nunca
     cierra con el total del departamento, y no es un error del mapa.
   - Una mesa de observados, mirada sola, parece imposible: 255 votos con 0 emitidos y 0
     habilitados.
2. **Hay mesas comunes con más votos emitidos que habilitados** (99 en las nacionales 2024, 105 en
   el balotaje). Son quienes votan observado fuera de su circuito: no es un error ni un fraude,
   pero sin explicarlo se presta a la peor lectura.
3. **Hay 9 mesas comunes sin habilitados** en las nacionales 2024, todas en departamentos de
   frontera (Treinta y Tres, Rivera, Artigas, Paysandú, Tacuarembó), donde todo voto es observado.
   Qué son exactamente es **a confirmar con la Corte**.
4. **El voto a un partido es hoja + lema.** `VOTO_LEMA` son los votos con varias hojas del mismo
   partido (válidos para el partido). Contar solo `HOJA_EN` subestima: el Frente Amplio suma
   1.061.334 por hoja y 10.492 por lema en las mesas de 2024.
5. **Los nombres cambian entre elecciones.** Columnas: `TipoRegistro` en 2024, `TIPO_REGISTRO` en
   2025. Partidos: «Partido Frente Amplio» en 2024, «FRENTE AMPLIO» en 2025. Tipo de circuito: `U`
   en 2024, `URBANO` en 2025. Comparar dos elecciones por nombre falla en silencio.
6. **La columna se llama `"Local "`, con un espacio al final.**
7. **El departamento viene en un código de dos letras propio** (`MO`, `FD` Florida, `FS` Flores,
   `RV` Rivera, `RO` Rocha…), que no es el ISO ni el del INE. Y los nombres llevan tilde
   («BELLA UNIÓN») donde el INE no («BELLA UNION»): cruzar por nombre pierde filas.
8. **127 mesas de los totales de 2024 no están en el plan circuital**: las 118 de observados y
   las 9 sin habilitados. Un cruce con `inner join` las pierde sin avisar.
9. **En las departamentales hay 2.152 mesas «SIN MUNICIPIO» y 3 con el municipio vacío.**

### Datos personales

El archivo de integración de las hojas trae, por cada uno de los 217.932 candidatos, **nombre,
sexo y número de credencial cívica**. El nombre de un candidato es público por definición; el
número de credencial es un identificador personal. **Un lector público de este paquete no debería
devolver la credencial.** Hasta dónde llega lo publicable, en particular para suplentes que nunca
asumen, es una pregunta **a confirmar con un asesor** (Ley 18.331 de protección de datos
personales).

### Control contra lo publicado

Frente Amplio, nacionales 2024, sumando hojas y lema:

| Qué | Votos |
|---|---|
| Todas las mesas (escrutinio definitivo, con observados) | 1.071.826 |
| Solo las mesas comunes | 1.059.379 |
| Escrutinio primario al 100% de los 7.234 circuitos ([Montevideo Portal](https://www.montevideo.com.uy/Noticias/Elecciones-nacionales-2024-segui-en-vivo-el-escrutinio-de-la-Corte-Electoral-uc904311), datos del 29/10/2024) | 1.058.625 |

Las mesas comunes difieren del escrutinio primario en 754 votos (0,07%), lo esperable entre el
conteo de la noche y el definitivo; las mesas de observados suman 12.447. **Falta contrastar el
total definitivo contra el resultado oficial de la Corte**, que es la fuente que vale, antes de
presentar cualquier número de este paquete como "el resultado".

## 4. Parlamento

### Forma

Un recurso por legislatura (de la 42, 1985, a la 50, la actual). Asistencias al Senado: ~110
legisladores por legislatura con citaciones, asistencias, faltas con y sin aviso, licencias.
Proyectos entrados: ~1.000 por legislatura con fecha, asunto, carpeta y título. Leyes promulgadas:
4.799, con el enlace al texto en IMPO.

### Las trampas

1. **Todos los recursos de un dataset tienen la misma URL final: `csv`.** Quien los guarda por el
   nombre de la URL pisa una legislatura con otra (le pasó a la medición de este documento).
2. **La nómina de diputados trae `Apellido, Nombre` con la coma sin comillas**: el nombre se parte
   en dos columnas y las filas tienen 7 u 8 campos según la persona.
3. **Codificaciones mezcladas en el mismo dataset**: los datos en UTF-8 y el archivo de metadatos en
   cp1252.
4. **Las remuneraciones son por cargo, no por persona**, con punto de miles (`569.694`).
5. **Las asistencias traen una columna con un tabulador pegado** (`'Faltas c/Aviso\t'`).

### Datos personales

Nombre, partido, departamento y correo institucional de legisladores: es información de su función
pública. La **edad** de cada diputado también viene en la nómina; no hace falta para nada de lo que
haría este paquete y conviene no devolverla.

## 5. Compras del Estado (ARCE, OCDS)

### Forma

Un archivo por año, 2002–2025. El catálogo lo declara **JSON y es un ZIP** (27 MB el de 2025) con un
JSON por mes de llamados (`l-MM`) y de adjudicaciones (`a-MM`), en el estándar internacional OCDS
1.1. En 2025: **110.063 adjudicaciones y 333.595 ítems**.

### Las trampas

1. **El formato declarado no es el del archivo**: «JSON» en el catálogo, ZIP en el disco.
2. **El importe es el precio unitario, no el total.** Solo 1.005 adjudicaciones traen un total;
   **222.616 ítems tienen cantidad distinta de 1**. Sumar `unit.value.amount` subestima el gasto.
3. **Las monedas están mezcladas**: pesos, dólares, euros, **Unidades Indexadas** (`UYI`), reales,
   francos suizos, rands, y **11.221 ítems sin moneda**. Sumar sin convertir no tiene sentido;
   convertir necesita la cotización del día (`uydatos.bcu`).
4. **3.146 registros son anulaciones de adjudicaciones** (`awardCancellation`): sumarlos cuenta
   gasto que no ocurrió.
5. **4.151 adjudicaciones no tienen proveedor.**

### Datos personales

El registro de proveedores (RUPE) incluye **personas físicas con nombre, RUT y domicilio fiscal**,
que en una empresa unipersonal es muchas veces la casa. El RUPE además mezcla UTF-8 en los datos y
cp1252 en el diccionario, y escribe los nulos como «Sin dato». Las adjudicaciones de OCDS traen el
nombre del proveedor. **Qué se puede exponer de una persona física proveedora del Estado** —su nombre
junto a lo que le vendió al Estado— es otra pregunta **a confirmar con un asesor**. Lo prudente para
empezar: agregados por organismo, rubro y año, y proveedores solo cuando son personas jurídicas.

## 6. Qué existe

No encontré proyectos abiertos que reutilicen estos datos con este nivel de cuidado: ni análisis de
OCDS de Uruguay en GitHub, ni mapas de resultados por circuito de terceros. El Parlamento prevé una
herramienta de visualización en su plan de gobierno abierto 2025–2029. La ARCE figura en el portal
internacional de Open Contracting.

## 7. Riesgos de publicar herramientas cívicas

- **Neutralidad.** La herramienta devuelve datos, no interpretaciones, y trata a todos los partidos
  igual. Ninguna nota del paquete opina sobre un resultado.
- **Un error electoral es un error público.** Este documento tuvo uno antes de publicarse: la
  primera versión decía que sumar las mesas no daba el resultado oficial, y lo que pasa es que los
  observados están en mesas especiales. Lo encontró el control contra lo publicado (§3). Por eso
  cada respuesta dice qué mesas suma y que los observados no tienen localidad.
- **Datos personales.** Ver §3, §4 y §5: credencial cívica, edad, domicilio de personas físicas. Lo
  que no se necesita no se devuelve.
- **Carga sobre los servicios públicos.** Todo se baja una vez y se guarda en caché.

## 8. Recomendación

| Orden | Qué | Por qué primero | Riesgo de datos personales |
|---|---|---|---|
| 1 | **`uydatos.elecciones`** y una herramienta MCP de resultados por departamento | Es lo que más público trae, los datos están completos y bien formados, y las trampas son pocas y medibles. **Hecho en 0.5.0.** | Bajo, si no se lee la integración de las hojas |
| 2 | **`uydatos.compras`** (OCDS): total = cantidad × precio, anulaciones fuera, monedas convertidas con el BCU | Es el dato con más valor periodístico y el que peor se lee sin ayuda | Medio: decidir qué se expone de personas físicas |
| 3 | **`uydatos.parlamento`**: asistencias, proyectos y leyes por legislatura | Bien formado, histórico largo | Bajo |

Para la comunicación, cada trampa de este documento es una nota corta posible: *«por qué sumar las
mesas no da el resultado oficial»*, *«el gasto del Estado no es la suma de los importes»*.
