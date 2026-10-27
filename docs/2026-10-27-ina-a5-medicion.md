# INA a5 (INFORM): nivel y caudal del río Uruguay — lo medido el 27/10/2026

Lector: `uydatos.ina`. Fuente de la tesis: el plan-2026-10-26 de `rastro-publico` marcó INA a5
como el paso 1 de la segunda pasada de fuentes (Concordia diaria desde 1931, Salto Grande
arriba/abajo). El mismo dato es el que publica el HTML de Prefectura: el plan-utilidad decidió
**no scrapear Prefectura** porque la altura está en INA a5 — medido acá, está y con fecha de
carga.

## 1. La fuente

- **Sistema**: INFORM (`alerta.ina.gob.ar`), el sistema de alerta temprana de la INA. Abierto,
  sin token, sin registro. El canal del nivel es `obs/puntual`.
- **La lista de estaciones**: `GET /a5/obs/puntual/estaciones` — 4.695 estaciones, con la
  metadata embebida (país, río, red, tabla, ítems has_obs, niveles de alerta).
- **El listado de series**: `GET /a5/obs/puntual/series` — 5.000 series en un JSON de 7 MB, la
  metadata de la estación embebida en cada una.
- **La metadata de una serie**: `GET /a5/obs/puntual/series/{id}` — el JSON de la estación, la
  variable y los niveles de alerta/evacuación/aguas bajas de la propia escala.
- **Las observaciones**: `GET /a5/obs/puntual/series/{id}/observaciones?format=csv` — **son
  obligatorios los cuatro query params `tipo`, `series_id`, `timestart`, `timeend`** (sin ellos
  responde `{"message":"query error","error":"Faltan parámetros…}`); el `tipo` va `puntual` y el
  `format=csv`. Cada dato es una **medición puntual** con `timeupdate` (la fecha de carga).
- El río Uruguay tiene **25 escalerías con serie H** en la red `escalas Prefectura Nacional`
  (serie_id = 60 a 99: Pepirí Miní, El Soberbio, San Javier, Yapeyú, Paso de los Libres,
  Mocosorá, Federación, **Salto Grande Arriba 77**, **Salto Grande Abajo 78**, **Concordia 79**,
  Colón 80, Concepción del Uruguay 81, Campichuelo 82, Boca Gualeguaychú 84, Gualeguaychú 99…).
  En este lector entran 77, 78, 79 (altura) y 926, 927, 928 (caudal), con sus rangos.

## 2. La medición (todas con hora de Uruguay)

| Serie | Variable | Ventana pedida | Filas | Bytes | sha256 (primeros 16) |
|---|---|---|---|---|---|
| 79 Concordia H | Altura (m) | 1931-01-01…2026-10-26 | 37.876 | 4.986.175 | `c78f3ad9d0871605` |
| 928 Concordia Q | Caudal (m³/s) | 1931-01-01…2026-10-25 | 33.118 | 4.425.584 | `0ebc9155d988f194` |
| 926 SG Arriba Q | Caudal (m³/s) | 1900-01-01…2026-10-25 | 12.273 | 1.633.142 | `f9a2d01718efa970` |
| 927 SG Abajo Q | Caudal (m³/s) | 1900-01-01…2026-10-25 | 8.178 | 1.087.934 | `2eed94b9b8b95d3e` |

La serie 926 arranca el **1995-05-01** (no en 2000: la ventana del 1900 lo reveló). El que fija
la prueba de regresión `-m red` es el rango cerrado 1931-1935 de la serie 79: **1.826 filas**.

Extremos medidos del histórico completo: H de Concordia **-0,24 a 17,82 m** (95 años, **0
valores vacíos**, el cero de la escala se pasa por debajo); Q de Concordia **197 a 35.389 m³/s**;
Q de SG Arriba **33,0 a 33.837** (desde 1995); Q de SG Abajo **0,0 a 30.437** (desde 2006).

Frescura del dato del día (medido el 27/10, ~02:00 UY): las alturas cargan el dato del día
entre las **12:43 y las 15:43 UY** (timeupdate del mismo día); los caudales de SG Arriba/Abajo
a las **18:01 UY**. El caudal de Concordia (928) **última fila del 15/07/2026: 3,5 meses de
atraso** y el API responde **cuerpo vacío** a su ventana reciente.

## 3. Las trampas, cada una con el número que la prueba

1. **El id es de serie, no de estación, y hay seis "Concordia" en 4.695 estaciones.** La
   estación 283 se llama **"CONCORDIA (DNCPVN-61…)" y es de Brasil** (`rio: RIO URUGUAI`,
   tabla `red_ana_hidro`, id_externo 78500000). Fijar una serie por nombre trae el dato de otra
   red sin avisarlo. El lector fija por id y trae la `metadata()` con el país para auditar.
2. **El API no valida el rango pedido.** Con `timestart > timeend` responde **HTTP 200 con
   cuerpo vacío** (medido). También responde 200 vacío una serie `has_obs: false` (la 938
   "Aporte Salto Grande", cuerpo sin encabezado). El lector valida `desde < hasta` antes de
   salir y levanta si el cuerpo no trae filas.
3. **La unidad no viene**: `unit_id` está vacía en las 37.876 filas medidas y la metadata no
   declara la unidad del `H`. La fija el lector (`H` = m, `Q` = m³/s), igual que los niveles de
   alerta de la escala (35,5 m en SG Arriba), que están en metros.
4. **La cadencia no es un dato por día**: 2.524 de los 34.932 días de Concordia traen 2
   lecturas, y 2 filas legítimas de 2024-10-23/24 vienen con la columna `nombre` vacía (la hora
   de la lectura del operador no es siempre 00:00: hay lecturas a las 10Z, 15Z, 09Z, 07Z, 11Z…).
   El lector no asume cadencia y no valida la columna `nombre`.
5. **52 de las 37.876 filas están a las 00-02Z**: su día local uruguayo es el anterior. El día
   local es una función con el desfase como parámetro (`dia_local(instante, desfase_horas=-3)`),
   no una constante.
6. **El filtro del API respeta el rango** (con `timeend 2015`, la última fila es del
   31/12/2015 —medido—) pero el lector valida igual: una fila fuera del rango pedido es la
   fuente dejando de comportarse.
7. **La cadena de cache sirve versiones viejas.** La primera consulta del día a la ventana de 7
   días de la serie 926 trajo filas hasta el 22/10; la segunda al mismo rango trajo el 26/10 y
   desde ahí quedó estable. `Cache-Control: no-store` no lo cambió. El lector no adivina: el
   sello guarda la hora de la bajada y la frescura es del `timeupdate`.
8. **El dato del día se carga por la tarde**: una tarea que corra al mediodía puede leer el dato
   de ayer sin que nada lo avise. El consumidor (rastro-publico) decide la frescura contra
   `timeupdate`, no contra el reloj de la bajada.

## 4. Lo que no se midió

- **Las series H1h/Hgeo1h/Q1h** (telemetría de la represa, con estación 78 y 79) y las
  derivadas `Hmm/Hmd/Hmmax/Hmmin/Qmd/Qmm/Qmmax/Qmmin/Fcat` (25 series por estación en total).
  El canal del río de este paso es el diario. Las subhorarias tienen otra vida (la del caudal de
  la represa contra el pronóstico de natas) y se miden cuando se usen.
- Las demás escalerías del río (60-99): la lista está acá arriba con los niveles de alerta, pero
  el lector no las trae al día hasta que alguien las consume (el semáforo de una playa de Fray
  Bentos, por ejemplo, usará la serie del 99).
- La tabla `alturas_bdhi` y las otras fuentes embebidas del listado (`red_ana_hidro`,
  `stations`, `red_inta`): fuera del alcance; solo se midió que por nombre se las confunde.

## 5. Decisiones que quedan registradas

- **El caudal de Concordia (928) entra al lector pero no al cron del consumidor**: con su
  atraso medido, una tarea diaria bajaría el historial 400 días por algo que no se actualiza.
  Para el semáforo el caudal lo aporta GloFAS y la CTM (comunicado y hidrometría), y el
  prerregistro no contrasta caudal contra floración con un solo episodio.
- **El `tipo` de las filas queda con el dominio cerrado a `puntual`** (medido en 37.876): si el
  API trae una fila con otro tipo (una serie agregada), el lector la rechaza en lugar de
  mezclarla con las mediciones.
- **Los rangos físicos van amplios y declarados** (H: -10 a 60 m; Q: 0 a 60.000 m³/s): el río
  puede estar bajo el cero de la escala (medido, -0,24) y el aforro máximo medido deja margen.
  Un valor nuevo fuera del rango es un defecto de la fuente, no un dato raro a declarar.