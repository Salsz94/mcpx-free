# MCPX-Free

Actualización del 21 de noviembre de 2026. La auditoría ampliada, sus 21 casos
reales y el siguiente desarrollo están en [PRUEBAS_REALES.md](PRUEBAS_REALES.md).
Este documento conserva el plan inicial y su historial.

Plan de desarrollo · 20 de noviembre de 2026 · Primera sesión prevista para el sábado 21 de noviembre

La X es un guiño a X-Men. MCPX-Free será un proyecto independiente para montar videos en DaVinci Resolve Free desde Codex, Claude Desktop y otros clientes MCP locales. La primera plataforma es Windows con Resolve Free **21.1.0.17**.

## El primer video

«Toma estos tres videos, pon B antes de A, termina con C, conserva el audio y aplica mi script de subtítulos». El resultado será una timeline nueva que se pueda abrir, revisar y corregir en Resolve. La primera entrega prioriza la precisión del montaje. Más adelante, el asistente podrá elegir fragmentos a partir de una entrevista y entregar un borrador mientras el usuario trabaja en otra cosa.

## Punto de partida

| Evidencia | Alcance |
|---|---|
| Comprobado en el equipo | Desde la consola Lua de Resolve Free se leyó el nombre del proyecto de prueba y se contaron sus timelines. La compilación devolvió 21.1.0.17. Se observaron `ffi` y `dofile` disponibles e `io` ausente. |
| Comprobado fuera de Resolve | En Windows se generaron FCPXML y SRT y se verificaron estructura, duración, URI y tiempos de subtítulos. Quedan pendientes la importación y la reapertura. |
| Evidencia de terceros | Creative Editor publica pruebas de edición sobre la misma compilación en Windows. AI Bridge documenta su transporte nativo en macOS Free. Sus resultados orientan el desarrollo. |
| Pendiente en este equipo | Intercambio de datos en vivo, descubrimiento por Codex y Claude, edición por MCP, persistencia, subtítulos del usuario y render. |

## Qué reutilizar

| Fuente | Decisión técnica |
|---|---|
| [Resolve Creative Editor](https://github.com/Anujpal-15th/resolve-creative-editor-mcp) | Partir de las operaciones editoriales, el proceso MCP por entrada y salida estándar y las pruebas con medios sintéticos. Revisar la conversión de rangos, preservación del audio y lectura posterior. Reemplazar el receptor que ejecuta el archivo de solicitud. Prescindir del motor adicional de Studio en la primera versión. |
| [Resolve AI Bridge](https://github.com/flamexnreal/davinci-resolve-ai-bridge-mcp/blob/main/docs/COMPATIBILITY.md) | Evaluar el acceso nativo a archivos de Fusion en Windows. Adoptar del protocolo la identificación de sesiones, firma, correlación y recuperación ante respuestas perdidas. Mantener el conjunto de operaciones autorizado dentro de Lua. El despachador genérico admite métodos elegidos por el remitente. |
| [Resolve Pilot](https://github.com/emircbngl/davinci-resolve-mcp-free/tree/2c9016faf22110517482f7a9efc71ef4e8439b8d/resolve_pilot/exporters) | Reutilizar los exportadores FCPXML y SRT para intercambio por archivos. Distinguir en los resultados archivo generado, archivo importado y montaje comprobado. |

Antes de incorporar código, fijar el commit de cada componente, revisar sus dependencias y conservar licencias, avisos y procedencia. Registrar qué archivos se toman y cuáles solo sirven de referencia.

## Arquitectura

```text
Codex o Claude Desktop
        │ MCP local por stdio
        ▼
MCPX-Free · servidor Python en Windows
        ├── plan de montaje y exportación FCPXML / SRT
        └── solicitud de datos validada e identificada
                    ▼
            puente Lua dentro de Resolve Free
                    ▼
            operación fija y lectura del resultado
```

El cliente propone una lista de edición. El servidor la valida completa y el puente ejecuta los cortes en una sola operación de montaje. Cada segmento identifica el medio, su rango de origen, la posición de destino y las pistas. Un único escritor por sesión evita que dos clientes intercalen cambios. Cuando se pierde una respuesta, se conserva el identificador de operación y se consulta la timeline antes de decidir cómo continuar.

La primera versión expondrá consulta del proyecto, listado de timelines, creación de un marcador de prueba y construcción de un montaje en una timeline nueva. El receptor Lua aceptará únicamente operaciones y argumentos definidos. El directorio de comunicación será privado para la cuenta de Windows y se comprobarán sus permisos efectivos. Los mensajes identificarán la sesión y el proyecto previsto. Las pruebas emplearán una biblioteca desechable, copias de medios y un directorio de salida dedicado.

## Jornada 1 · Conexión y cortes

### 1. Preparar el entorno

- Tener tres clips distinguibles, al menos uno con voz, el nombre o archivo del script de subtítulos y un ejemplo del tipo de video buscado.
- Preparar la biblioteca desechable y una timeline a 30 fps. Registrar edición, compilación y cliente empleados. Mantener el trabajo en una carpeta propia de MCPX-Free.
- Revisar scripts de instalación y cambios previstos. Solicitar autorización antes de instalar terceros, registrar servidores en la configuración del cliente o hacer operaciones destructivas. Hacer primero las comprobaciones que puedan ejecutarse de forma aislada.

### 2. Probar el recorrido completo

Dedicar inicialmente **90 minutos** a esta exploración. Comprobar primero que Fusion puede leer una solicitud de datos y devolver una respuesta en una ruta de Windows con espacios. Después arrancar el servidor por stdio, descubrir sus herramientas desde Codex y consultar el proyecto A. Abrir el proyecto de prueba B y repetir. Detener el puente y comprobar que el cliente informa de la desconexión.

**Decisión:** si devuelve ambos nombres correctos y detecta la desconexión, probar un marcador, leer su fotograma, guardar y reabrir. Si falla el intercambio seguro, documentar la operación exacta que falla y pasar al montaje por FCPXML con importación manual. El plazo limita la investigación del transporte y preserva el tiempo dedicado al video.

### 3. Montar una secuencia con resultado conocido

Usar fotogramas enteros en esta prueba y rangos de origen con entrada incluida y salida excluida. Convertir una sola vez a la convención que espere el método de Resolve. Las posiciones de destino son relativas al primer fotograma de la timeline.

| Orden | Origen a 30 fps | Destino | Duración |
|---|---|---|---|
| B | 60 a 180 | 0 a 120 | 120 fotogramas |
| A | 30 a 120 | 120 a 210 | 90 fotogramas |
| C | 0 a 150 | 210 a 360 | 150 fotogramas |

**Aceptación:** comprobar orden B–A–C, rango de cada medio, cortes en 120 y 210, duración total de 360 fotogramas, ausencia de huecos y audio sincronizado. Verificar la imagen anterior y posterior a cada corte. Guardar, cerrar el proyecto, reabrirlo y repetir la lectura. Registrar si se logró por MCP en vivo o por importación manual.

### 4. Probar fallos que estropean un montaje

- Un medio ausente o un rango fuera de sus límites debe detectarse antes de escribir.
- Si cambia el proyecto o la timeline entre la vista previa y la ejecución, detener la operación.
- Ante un fallo parcial, identificar la timeline de borrador y los segmentos ya colocados. Una reconexión no debe duplicarlos.
- Cortar la conexión después de enviar un marcador y antes de recibir respuesta. Recuperar el estado y comprobar que el marcador aparece una sola vez.
- Repetir después con medios habituales del usuario, fps fraccionarios o mezclados y audio separado si forman parte de su trabajo. Medir la duración en la base de tiempo real de la timeline.

## Jornada 2 · Subtítulos y primer video útil

Identificar cómo se usa hoy el script del usuario, qué recibe, qué modifica, qué produce y si consume un servicio de pago. Si genera SRT, procesar el audio del montaje terminado y comprobar los tiempos antes de importar. Si escribe títulos o subtítulos en Resolve, verificar el proyecto y la timeline antes de ejecutarlo y leer después los elementos creados. Si necesita una ventana manual, registrar ese paso y mantenerlo visible en el resultado.

Exponer una acción específica para el script revisado. Probar una frase que empiece inmediatamente después de un corte y otra próxima al final. Ejecutarlo por segunda vez para comprobar cómo gestiona subtítulos existentes. El primer video útil será una pieza del formato habitual del usuario. Anotar minutos de trabajo y de corrección manual, problemas de audio o texto y si el borrador quedó listo para publicar.

## Jornada 3 · Dejar un encargo en marcha

Empezar con una entrevista corta. Pedir un borrador de 45–60 segundos, con frases completas y sin repeticiones. Obtener una transcripción con tiempos y, si las decisiones dependen de imagen, fotogramas de referencia. El asistente elegirá fragmentos y conservará la lista de cortes. El servidor construirá una timeline nueva, validará el montaje y aplicará subtítulos. Si se solicita MP4, esperará el render y comprobará que el archivo abre, contiene video y audio y tiene la duración esperada.

El objetivo inicial es terminar mientras el chat y Resolve permanecen activos. Registrar el avance localmente para recuperar un trabajo interrumpido. La ejecución tras cerrar el cliente o reiniciar Windows se evaluará por separado cuando el flujo interactivo sea fiable.

## Compatibilidad, coste y publicación

- **Codex y Claude Desktop.** Ejecutar el mismo caso B–A–C desde ambos en timelines distintas. Comparar rangos, duración, audio y estado final. Publicar resultados por cliente y versión.
- **Presupuesto inicial.** Objetivo de cero gasto adicional con Resolve Free, herramientas locales y el uso incluido en la cuenta. Registrar cualquier dependencia opcional con coste, especialmente transcripción o servicios que utilice el script existente.
- **GitHub.** Preparar ejemplos con medios sintéticos, instalación y desinstalación en Windows, licencias, avisos de terceros y una matriz de compatibilidad por compilación. Excluir claves, registros con rutas personales, material de clientes y scripts privados. Publicar solo después de revisar el contenido y contar con autorización.
- **Criterio para anunciar una función.** Distinguir implementación, prueba automatizada, prueba real en Resolve y persistencia tras reabrir. Un servidor iniciado o una herramienta registrada acreditan únicamente esa etapa.

## Entregas y decisión de continuidad

| Hito | Evidencia necesaria |
|---|---|
| Primer día aprovechado | Montaje B–A–C conservado después de reabrir, con método de ejecución identificado. |
| Primera versión en vivo | Consulta desde Codex, marcador persistente, cortes verificados y recuperación sin duplicados. |
| Primera versión útil para el usuario | Video habitual terminado con subtítulos correctos y medición del tiempo y las correcciones. |
| Primera versión pública | Instalación reproducible, material de prueba distribuible, licencias y límites conocidos. Cada cliente anunciado supera la misma prueba. |

Si solo pasa la ruta FCPXML, entregar ese flujo con su paso de importación documentado. Si también pasa el puente, concentrar la siguiente iteración en los cortes y subtítulos que más tiempo ahorren al usuario.

## Avance comprobado en Windows · 20 de noviembre de 2026

Actualización de reutilización. Se fijó Creative Editor a `1a5879173c59b736ddd9279b65e77e28037fa671` y se incorporó su función de análisis de timeline con licencia MIT y procedencia conservadas. La lectura real de V1/A1 devolvió seis clips y cero huecos o solapamientos. Se adaptó el bucle de propiedad de sesión para despachar solicitudes continuamente. El arranque único y las consultas posteriores funcionaron en Resolve Free 21.1.0.17. Se corrigieron el falso positivo de pistas equivocadas y el cierre por cabecera truncada. Se ejecutaron seis pruebas automatizadas y la simulación del receptor Lua y del servidor MCP.

- Resolve Free 21.1.0.17 aceptó el buzón privado de datos por Fusion desde la consola Lua. La ruta inicial se realiza con despacho explícito de cada solicitud. La ACL y la correlación del ID protegen el canal local. Una entrada de montaje importa un FCPXML generado en el buzón y vuelve a leer la timeline.
- Dos proyectos desechables devolvieron estados distintos. En A quedaron el montaje por el menú de importación y un marcador persistente en 120. En B, el montaje solicitado por MCP pasó la verificación de video y audio y se conservó tras reabrir. La repetición del mismo ID dejó una sola timeline.
- Codex descubrió las herramientas de inspección y marcador mediante configuración temporal. La edición completa se hizo con el cliente MCP de prueba. La instalación y las verificaciones figuran en el [README](README.md) y la [auditoría](AUDITORIA.md).
- Siguiente prioridad: repetir el montaje desde Codex y Claude, verificar imagen y señal de audio en los cortes, y ejecutar con material habitual en la biblioteca desechable. Después incorporar el script de subtítulos revisado. El arranque continuo, render y nuevos mecanismos de edición quedan sujetos a pruebas antes de exponerlos.
# Roadmap de puesta en marcha · 20 de noviembre de 2026

| Orden | Trabajo | Criterio para avanzar |
|---|---|---|
| 1. Probar hoy en esta máquina | Con el receptor activo, ejecutar desde esta carpeta `python smoke.py --session .scratch/private-ipc request_inspection` y consultar el ID con `resolve_result`. Para una sesión nueva seguir la preparación y el arranque Lua del README. | La respuesta identifica Resolve Free, la versión y el proyecto de prueba previsto. Esta etapa pasó en la sesión actual. |
| 2. Validar el cliente de uso diario | Desde una conversación de Codex, pedir inspección, previsualizar B–A–C, montar en una timeline nueva y leerla. Guardar y reabrir. Repetir desde cada cliente Claude que se vaya a anunciar. | Por cliente, conservar versión, ID y lectura tras reabrir con seis elementos, dos cortes y 360 fotogramas. El registro persistente requiere la autorización del operador. |
| 3. Comprobar la salida audiovisual | Renderizar los 12 segundos sintéticos y comprobar el cambio de imagen y tono alrededor de los fotogramas 120 y 210. | Orden B–A–C en imagen y audio, duración esperada y cortes sincronizados en el archivo exportado. |
| 4. Probar recuperación y escala | Detener y reanudar el receptor en la biblioteca de pruebas, verificar el resultado antes de repetir una escritura y ensayar una respuesta superior al límite del lector. | Una sola timeline para el mismo ID. Ante una respuesta grande, lectura completa o diagnóstico explícito. Ante una importación parcial, identificar el borrador y documentar la recuperación. |
| 5. Pilotar un video habitual | Copiar medios representativos a la biblioteca desechable. Verificar formato, FPS, audio y origen. Montar un fragmento, medir correcciones y comparar con la edición manual. Incorporar el script de subtítulos después de revisarlo con una muestra. | El usuario aprueba imagen, sonido y sincronía del render con sus propios medios. Registrar qué formatos y qué cliente pasaron antes de ampliar el uso. |

## Arranque accesible desde Resolve

El activador del menú Scripts reemplaza el pegado de código en el uso habitual.
El panel local muestra actividad reciente y permite detener el receptor. Se
verificó el arranque por menú con el operador y una consulta real por MCP. La
simulación cubre desconexión, reconexión y configuración entre scripts aislados.
El panel requiere Python y Tkinter. El empaquetado como exe autónomo sigue
pendiente. Al abrir otra sesión de Resolve se vuelve a seleccionar MCPX Free
en el menú. La sesión del panel y la del cliente MCP deben coincidir.
