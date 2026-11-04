# El MCP de data.gouv.fr: qué se toma, qué se rechaza

Fecha: 2026-11-04. Leído el repositorio `datagouv/datagouv-mcp` en el commit `136f1bb`
(2026-11-03), clonado entero. El retorno de experiencia de la DINUM (julio de 2026) **no se leyó**
en la fuente: `numerique.gouv.fr` y `guides.data.gouv.fr` no resolvían desde la máquina de la
medición. Lo que se cita de él viene de la prensa (Next, Alliancy, Banque des Territoires, ActuIA)
y va marcado como tal.

## 1. Qué es

| Qué | Valor | De dónde |
|---|---|---|
| Herramientas | 10, todas de solo lectura | `tools/*.py` |
| Con `ToolAnnotations` (`readOnlyHint`, `idempotentHint`, `openWorldHint`) | 10 de 10 | `helpers/mcp_tool_defaults.py` |
| Transporte | solo Streamable HTTP; instancia pública sin clave en `mcp.data.gouv.fr/mcp` | README |
| Versiones | 34 en el CHANGELOG, 1.0.0 el 2026-09-04 | `CHANGELOG.md` |
| Uso medido | un evento de Matomo **por llamada a herramienta**; desde 0.2.28 ya no por request | `helpers/matomo.py`, CHANGELOG |
| Evaluación de las respuestas del modelo | **ninguna** escrita | README, `tests/` |

## 2. Lo que dice la DINUM, según la prensa

- «Es muy difícil auditar los resultados de un servidor MCP» (Next, Alliancy).
- Un tester lo describe como **un explorador, no una herramienta de extracción en volumen**.
- No abre datos nuevos: cambia la interfaz de los ~74.000 datasets que ya eran públicos.
- Avisa que hay servidores MCP **no oficiales que se presentan como suyos**.

La primera frase es la tesis de este paquete dicha por el que tiene más recursos: el MCP oficial
pasa el dato tal como llega, y auditarlo queda del lado de quien lo usa. Acá el lector rechaza y el
sello (`uydatos.procedencia`) dice de qué archivo salió la cifra.

## 3. Qué se toma

| Qué | Dónde va | Estado |
|---|---|---|
| El script que hace etiqueta + Release + notas de una vez (`tag_version.sh`) | `scripts/publicar.sh`, con las notas del CHANGELOG y simulación por defecto | hecho, sin publicar |
| Un aviso cuando `main` tiene una versión que no está en PyPI | trabajo `sin-publicar` en `tests.yml`: avisa, no publica | hecho, sin publicar |
| Decir que no es oficial | README, «No es oficial» | hecho, sin publicar |
| Un canal de feedback (ellos usan un formulario Tally) | plantillas de issue: fuente que cambió, fuente nueva (con la pregunta que contesta) | hecho, sin publicar |
| Política de contribuciones con IA («quien abre el PR responde») | `CONTRIBUTING.md` | hecho, sin publicar |
| `ToolAnnotations` en cada herramienta | `mcp-uruguay` | pendiente |
| El flujo de uso escrito en la descripción de la herramienta (buscar → listar → previsualizar) | `mcp-uruguay` | pendiente |
| Errores que dicen qué valores sirven, para que el modelo se corrija solo | `mcp-uruguay`: el motivo de la excepción ya está, falta decir qué probar | pendiente |

## 4. Qué se rechaza

| Qué | Por qué no |
|---|---|
| Buscar en todo el catálogo como herramienta central | Lo hace el oficial y lo hace `uruguay-mcp`. La razón de este paquete es leer pocas fuentes bien. |
| Telemetría por llamada | `mcp-uruguay` corre local con `uvx`: medir a cada usuario sin que lo pida no va. La señal barata son las descargas de PyPI por versión y los issues. |
| Instancia pública por HTTP, por ahora | Necesita health check, tests de carga, protección SSRF y preproducción (los cuatro están en su repo). Se decide con demanda medida, no antes. |
