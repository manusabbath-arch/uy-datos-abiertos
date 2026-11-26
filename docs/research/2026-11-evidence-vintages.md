# Evidencia recuperable y revisiones — propuesta 2026-11-26

No reemplaza uydatos.fuentes, uydatos.verificar ni uydatos.revisiones. El objetivo es cerrar el espacio entre detectar un cambio y reconstruir el insumo exacto.

## Referencias de diseño (pendiente auditoría comparativa completa)
- https://alfred.stlouisfed.org/ — distinguir período de observación y versión conocida.
- https://www.w3.org/TR/prov-overview/ — entidad, actividad y agente como vocabulario conceptual.
- https://www.researchobject.org/ro-crate/ — empaquetado de evidencia.
- https://frictionlessdata.io/ — contratos de datos.
- https://www.open-contracting.org/ — indicadores de riesgo; identificar campos reales antes de implementar.

## Contrato mínimo propuesto
Versión de esquema, identificador de fuente, URL original si conocida, instante de descarga UTC, período observado si conocido, fecha de publicación si consta, SHA-256 de bytes crudos, tamaño, versión de lector, parámetros de transformación, estado de calidad, referencia recuperable o motivo de no retención. Separar metadatos de observación y de ejecución. No rellenar ausencias con fechas inferidas. Hash no equivale a autenticidad ni disponibilidad.

## Diseño de almacenamiento
Piloto local opt-in de objetos por SHA-256, escritura atómica y verificación al recuperar. Catálogo de adquisiciones separado: dos URLs o fechas pueden apuntar al mismo objeto. No sobrescribir objetos ni afirmar que una adquisición equivale a fecha de publicación. Una consulta as-of solo puede afirmar lo observado en el archivo local hasta la fecha, no reconstruir versiones nunca capturadas. Retención explícita por fuente: revisar licencias, privacidad, tamaños y costo; excluir inicialmente sanciones y datos personales. No publicar datos crudos por defecto.

## Pruebas propuestas
Bytes idénticos/diferentes; dos adquisiciones del mismo objeto; corrupción y ausencia; fallo a mitad de escritura; fecha desconocida; revisión de períodos anteriores; restauración; política de no retención; concurrencia; rutas no confiables. Sin red por defecto y sin dependencias obligatorias nuevas. Integrar con salida existente de revisiones tras inspeccionar sus contratos, no duplicar lógica.

## Piloto de alto retorno
Seleccionar una serie económica BCU o INE con revisiones observables y condiciones compatibles; medir tamaño, frecuencia real y recuperación. Comparar contra baseline actual. Luego evaluar catálogo público de salud de fuentes derivado de verificaciones existentes, sin confundir retraso con periodicidad no declarada.

## Compras públicas
Antes de implementar indicadores OCP, crear matriz indicador/campo/cobertura/unidad/sesgo/criterio de abstención. Cantidades y precios problemáticos de ARCE bloquean inferencias de precio unitario cuando no hay unidad válida. Una alerta no demuestra corrupción.

## Pendiente
Auditar contratos de caché y revisiones, licencias por fuente, ejecutar pruebas y medir almacenamiento. Este documento no implementa ni promete conservación.
