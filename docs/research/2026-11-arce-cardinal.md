# ARCE y Cardinal: auditoría preliminar de aplicabilidad

Fuentes consultadas 2026-11-26:
- https://www.open-contracting.org/resources/red-flags-in-public-procurement-a-guide-to-using-data-to-detect-and-mitigate-risks/
- https://cardinal.readthedocs.io/en/latest/cli/indicators/
- https://cardinal.readthedocs.io/en/latest/cli/indicators/R/018.html
- https://data.open-contracting.org/en/publication/42 (histórico)
- https://data.open-contracting.org/en/publication/43 (API)
- https://www.gub.uy/agencia-reguladora-compras-estatales/datos-y-estadisticas/datos-abiertos

## Hallazgos de código
src/uydatos/compras.py, blob 5662d27e487d3660d6c5f758f25239914a0e11bc:
- leer_adjudicaciones filtra tag award y conserva solo suppliers[0]. No permite inferir número de oferentes ni todos los adjudicatarios. No afirmar frecuencia real de adjudicaciones multiproveedor sin medir.
- _items usa quantity=1 y amount=0 ante campo ausente. Contrastar contra contrato fuente y medir antes de modificar; registrar ausencia explícitamente, distinguir cero real de ausente. _numero acepta float no finito; probar NaN/infinito en fixture y decidir rechazo.
- fecha proviene de release.date, no necesariamente fecha de adjudicación.
- No conserva id de award ni unidad en items; ocid solo no identifica award ni versión.
- Estado active no equivale a desembolso efectivamente pagado; revisar docstrings y comunicaciones.
- No se ha medido en esta pasada cobertura de esos campos ni frecuencia de defaults.

## Matriz inicial (no resultados calculados)
| Candidato | Campos mínimos | Estado |
|---|---|---|
| R018 oferta única | tender.numberOfTenderers o tenderers completos según definición, procurementMethod competitivo | Bloqueado lector actual; inspeccionar llamados; un proveedor ganador no prueba oferta única |
| Concentración por recuento | buyer.id, award.id, suppliers completos, estado, OCID, versión | Parcial; medir duplicados, IDs y multiproveedor; definir denominador |
| Concentración monetaria | anteriores, valor válido, moneda, alcance | Bloqueado para inferencia robusta por extremos conocidos |
| Plazo de presentación | tender.tenderPeriod.startDate/endDate, método | Requiere llamados y comparabilidad |
| Precio unitario atípico | clasificación, unidad, cantidad, moneda, fecha, especificación | Bloqueado hasta validar unidades y valores |
| Modificaciones/renovaciones | contracts/amendments, versiones | Registry API advierte extensiones/renovaciones no incluidas; no asumir cobertura histórica |
| Calidad de datos | faltantes, estados, monedas, duplicados | Candidato inmediato, no indicador de corrupción |

Cardinal puede servir como referencia externa; no incorporar Rust ni transformar datos en silencio. Reportar evaluable/no evaluable/flag/no flag separados: Cardinal puede omitir resultados tanto por falta de datos como por ausencia de bandera.

## Plan de medición
Capturar archivo autorizado con hash, listar llamados y adjudicaciones por mes, medir cobertura de campos por método/organismo/año, contar releases y awards por identificador, separar datos ausentes de inválidos, verificar relación por OCID. Comparar con Cardinal sobre fixture OCDS sintético; luego muestra real si acceso y licencia permiten. Publicar agregados, no identificadores personales innecesarios. No inferir corrupción ni gasto pagado.
