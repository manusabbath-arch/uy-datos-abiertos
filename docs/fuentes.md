# El contrato observado de las fuentes (informe del 2026-10-19)
ancap            26618 filas  anio, mes, producto, precio, unidad
ancap_ventas      1223 filas  mercado, anio, mes, familia, linea, bandera, cantidad, unidad
bcu                 30 filas  fecha, valor
catalogo            --       no es una fuente: se mide con `python -m uydatos.catalogo --faltantes`
compras         140144 filas  ocid, fecha, comprador, proveedor, estado, items, importes, sin_moneda
elecciones        7352 filas  opciones, codigo_departamento, departamento, crv, serie, habilitados, emitidos, no_observados, observados, anulados, en_blanco, municipio, tipo
hojas               --       necesita un archivo de planilla
ibge               562 filas  periodo, valor
ideuy               --       necesita una dirección
indec              117 filas  periodo, valor
inia             20526 filas  fecha, temperaturaMaxima, temperaturaMinima, pluviometro
inumet          393534 filas  fecha, estacion, temp_aire
limites             20 filas  codigo, nombre, departamento, tipo, datos, bbox, poligonos
mides               --       necesita un número de indicador
observatorio        --       necesita un slug de indicador
parlamento         508 filas  fecha, asunto, carpetas, titulo, tipo
rut                 --       no lee una fuente: calcula el dígito verificador
salto_grande        --       necesita una estación y una variable
sanciones         1528 filas  razon_social, nombre_comercial, rut, departamento, fecha, motivo, tipo, monto_ur
semanas             --       no lee una fuente: cuenta semanas ISO
ursea              580 filas  inicio, fin, vigencia, dias, producto, sin_impuestos, sin_impuestos_con_agro, con_impuestos
