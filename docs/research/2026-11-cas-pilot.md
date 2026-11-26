# Piloto CAS / ALFRED — especificación mínima

Referencia primaria: https://alfred.stlouisfed.org/help/downloaddata . ALFRED distingue períodos de vigencia de valores revisados. Nuestro archivo local solo puede afirmar cuándo observó bytes, no cuándo estuvieron disponibles al público si no consta.

## Contrato
Objeto = bytes + SHA-256 + longitud. Adquisición = identificador de fuente, URL saneada, instante UTC de captura, digest, fecha de publicación opcional con evidencia, versión de lector. Múltiples adquisiciones pueden apuntar a un objeto. Observaciones y transformaciones son entidades separadas. No retener datos personales por defecto.

## Implementación experimental
CAS opt-in, stdlib, directorio privado, ruta derivada únicamente de digest validado. Escribir temporal en mismo filesystem, flush/fsync, publicar atómicamente; si objeto existe comprobar bytes/hash antes de reutilizar. No sobrescribir corrupción silenciosamente. Catálogo append-only o SQLite transaccional; registrar adquisición solo después de confirmar objeto durable. Un objeto huérfano no es una adquisición; recuperación y limpieza explícitas. No prometer inmutabilidad frente al dueño del filesystem.
Consulta as-of selecciona adquisiciones capturadas hasta instante solicitado, sin extrapolar a períodos sin captura. Retención por fuente y presupuesto; borrado solo con política explícita y registro de pérdida de reproducibilidad.
Pruebas sintéticas: deduplicación, cambio de bytes, digest inválido, corrupción, falta, concurrencia, fallo antes/después de publicación, UTC, empate temporal, no retención. Medir espacio y tiempo; integrar con verificaciones existentes solo tras auditar contratos. No se ha ejecutado prototipo en esta pasada.
