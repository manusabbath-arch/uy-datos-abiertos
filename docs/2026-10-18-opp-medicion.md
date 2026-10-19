# La OPP: 19 datasets, y 18 congelados

Fecha: 2026-10-18 (hora de Montevideo). Medido con `uydatos.catalogo` contra
`catalogodatos.gub.uy`, un pedido por vez.

## La medición

```sh
uv run --quiet python -c "
from uydatos import catalogo
r = catalogo.accion('package_search', q='organization:opp', rows=30)
print(r['count'])
for d in sorted(r['results'], key=lambda d: d['name']):
    fechas = sorted((x.get('last_modified') or '')[:10] for x in d.get('resources') or [])
    print(d['metadata_modified'][:10], len(d.get('resources') or []), fechas[-1], d['name'])
"
```

`count` = **19**. La columna `metadata_modified` es la fecha que el catálogo declara para la ficha;
la última es la del recurso más nuevo, que es la que dice cuándo se publicó un dato.

| Dataset | Recursos | Último recurso | metadata_modified |
|---|---|---|---|
| opp-cantidad-de-rrhh-en-eepp | 2 | 2021-01-13 | 2021-03-11 |
| opp-clasificacion-funcional-del-presupuesto-con-indicadores | 5 | 2021-03-09 | 2022-07-11 |
| opp-compromisos-de-gestion-de-eepp | 2 | 2021-01-13 | 2021-03-11 |
| opp-credito-presupuestal-detallado-a-partir-de-2011 | 14 | 2021-03-09 | 2022-07-11 |
| opp-evaluaciones-de-intervenciones-publicas | 2 | 2021-03-10 | 2021-03-11 |
| opp-historico-de-credito-presupuestal-ejecutado | 5 | 2017-12-06 | 2020-12-15 |
| opp-historico-de-credito-y-ejecucion-presupuestal-por-ue | 2 | 2016-07-01 | 2020-12-15 |
| opp-indicadores-financieros-de-eepp | 3 | 2021-01-13 | 2021-03-11 |
| opp-ingresos-y-egresos-de-los-gobiernos-departamentales-y-egresos-de-los-gobiernos-municipales | 14 | 2024-08-29 | 2024-08-29 |
| opp-listado-de-empresas-publicas | 2 | 2021-01-13 | 2021-03-11 |
| opp-listado-de-personas-publicas-no-estatales | 3 | 2021-01-13 | 2021-03-11 |
| opp-monto-ejecutado-en-proyectos-de-inversi-n | 2 | 2012-12-05 | 2021-03-11 |
| opp-objetivos-de-desarrollo-sostenible-y-sus-metas | 2 | 2021-01-13 | 2021-03-09 |
| opp-organismos-del-presupuesto-nacional | 3 | 2021-03-09 | 2022-07-11 |
| opp-planificacion-estrategica-de-organismos-y-ues | 5 | 2021-03-09 | 2021-03-11 |
| opp-presupuestos-quinquenales | 3 | 2021-03-09 | 2021-09-06 |
| opp-productos-de-las-unidades-ejecutoras | 2 | 2021-03-09 | 2021-07-23 |
| opp-sociedades-anonimas-en-que-participan-eepp | 5 | 2021-01-13 | 2021-03-11 |
| opp-vinculo-entre-ods-y-planificacion | 2 | 2021-01-13 | 2021-03-11 |

Los nombres son los del catálogo, sin corregir: `opp-monto-ejecutado-en-proyectos-de-inversi-n`
perdió la «ó» al publicarse, y el de gobiernos departamentales tiene 94 caracteres y repite «egresos
de los gobiernos».

## Dos cosas que la tabla dice sin querer

**1. La fecha del metadato no es una revisión.** Tres datasets declaran `metadata_modified` de
2022-07-11 y sus recursos son de 2021-03-09: alguien tocó la ficha y no volvió a subir un archivo.
Es la misma lección que ya está medida con las sanciones del DSS, donde el archivo tenía el mismo
sha256 que dos meses antes con `metadata_modified` de 2026-03-22. Por eso `uydatos.fuentes.deriva()`
pregunta la fecha del recurso y no la de la ficha.

**2. El bloque no es una serie viva.** El último recurso nuevo es de **2021-03-09**. Lo que hay
adentro mira hacia atrás: `opp-historico-de-credito-y-ejecucion-presupuestal-por-ue` llega a
2016-07-01 y `opp-monto-ejecutado-en-proyectos-de-inversi-n` a 2012-12-05. Es una foto del
quinquenio 2015-2020, no una fuente que se actualice.

## La decisión

**No se escribe el lector.** Un lector ahí devuelve series que terminan hace cinco años, y el
paquete no tiene manera de decir «esto está muerto» sin que el que lo usa lo lea. Un lector que hay
que acompañar con una advertencia en cada llamada no es un lector: es una trampa con documentación.

El único dataset con datos frescos (2024-08-29) es el de ingresos y egresos de los gobiernos
departamentales, y son 14 recursos con estructura propia: si en algún momento hace falta, se mide
solo ese, con su propia trampa y su propio test, y no arrastra a los otros dieciocho.

Si hace falta el presupuesto vigente, el dato no va a venir de acá: hay que buscarlo en el portal de
Presupuesto Abierto o en la ejecución presupuestal que publica el MEF, que son otros datasets, y
medirlos antes de escribir nada.

Lo que queda hecho: la pregunta cerrada. Cuando alguien vuelva a proponer el lector de la OPP, este
doc le contesta con la tabla en vez de con una impresión.
