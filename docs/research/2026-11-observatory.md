# Uruguay Data Observatory — MVP dentro de uydatos

Nombre provisional; no institución oficial. Producto: informes fechados, reproducibles, con alcance y denominador explícitos. No otro catálogo ni ranking de organismos. No confundir lectura exitosa con vigencia, integridad o exactitud. Separar disponibilidad, parseabilidad, actualidad declarada, revisiones, procedencia recuperable y comparabilidad. Sin puntuación compuesta inicialmente.

## Hallazgo interno UDO-001
Fuente: docs/fuentes.json, fecha declarada 2026-10-19. 21 entradas, 13 ok, 8 no ok. BCU e INIA: mismo digest a4e1876d4d8f5fdcdc5bc483ec443b6cdbcbc2ce713a1c651e68ad3251acad3d y 49106270 bytes. No es verificación nueva. Hipótesis: verificar.main pasa el mismo destino a cada lector y _sha(directorio) incluye todos los archivos; _de_bcu y _de_inia devuelven directorio. Reproducir con adaptadores sintéticos, destino compartido y aislado; luego comprobar en red autorizada. No atribuir fallo a organismos. El histórico no demuestra causa ni permite recuperar bytes. Revisar también _de_ina que devuelve directorio sin escribir archivos explícitamente; comprobar si el sello representa insumo real.

## MVP offline
python -m uydatos.integridad_publica docs/fuentes.json
Consume contrato existente, no descarga; devuelve fecha original, hash del informe, recuentos y alertas de sellos compartidos. No publica motivos crudos. No distingue automáticamente no medido de fallo sin metadatos históricos suficientes. No usar uydatos.observatorio (lector de otro servicio). Tests sintéticos incluidos, pendientes de ejecución en CI.

## Siguiente gate
Aislar cada adquisición y conservar manifiesto por archivo; medir y documentar el defecto antes de modificar API. Separar no aplicable/no medido/error de acceso/rechazo del lector mediante campo explícito en futuros informes. Elegir 20–50 recursos con periodicidad declarada, no extrapolar lectores a datasets. Registrar frecuencia, URL, fecha de observación, evidencia y tolerancia justificada. Publicar primer boletín solo tras revisión humana de hallazgos, con mecanismo de corrección y enlace al método. Sin nuevo repo, sitio, API o cron hasta validar el piloto.
