# Auditoría de factibilidad

## Reutilización y correcciones posteriores

Creative Editor se descargó y fijó al commit `1a5879173c59b736ddd9279b65e77e28037fa671`. Su licencia MIT se conserva en el repositorio. Se extrajo la función `analyze` y se conectó con una nueva lectura real de los clips por pista. El resultado de la prueba en Resolve Free 21.1.0.17 fue V1 con tres clips, A1 con tres clips y cero huecos o solapamientos.

El receptor continuo adapta el patrón de propiedad de sesión del puente de Creative Editor. Se inició una sola vez en la consola de la biblioteca desechable. Después respondió a una consulta de entorno y ejecutó un montaje por MCP, cuya lectura devolvió `verified_import`, tres clips de video y 360 fotogramas. Esta última timeline usa el nombre ligado al ID de su operación. Su persistencia después de reabrir queda pendiente.

La simulación reprodujo y corrigió dos fallos. El verificador ahora rechaza elementos de montaje en V2/A2. El servidor devuelve un error comprensible ante una cabecera truncada y sigue atendiendo herramientas. Pasaron seis pruebas Python y el recorrido simulado que ejecuta el receptor Lua real contra objetos de prueba. La corrección de pistas también se ejecutó durante el montaje real en V1/A1. El rechazo de V2/A2 se comprobó mediante simulación.

El modo continuo queda activo en la sesión de prueba al terminar esta comprobación. La detención se hace con `fusion:SetData("MCPX.WorkerOwner", nil)`. Siguen pendientes el render y su señal de audio, los clientes conversacionales, las operaciones sobre clips existentes y el script de subtítulos del usuario.

La aplicación instalada se identificó desde dentro de Resolve como `DaVinci Resolve` **21.1.0.17**. En Windows, la consola Lua cargó el receptor con `dofile` y Fusion leyó y escribió archivos con `OpenFile`, incluso en una ruta con espacios. El manual de Blackmagic reserva el ajuste de scripting externo para Studio. La matriz oficial también asigna la integración nativa de asistentes a Studio. El resultado local acredita Lua dentro de la compilación medida. [Manual de Resolve](https://documents.blackmagicdesign.com/UserManuals/DaVinciResolveReferenceManual.pdf) · [Matriz oficial 21.1](https://documents.blackmagicdesign.com/SupportNotes/DaVinci_Resolve_Studio_21_Features.pdf?_v=1790578810000)

## Repositorios candidatos

La compatibilidad indicada en esta tabla procede de los mantenedores o de sus issues. MCPX-Free no ejecutó los instaladores de terceros. Las cifras de actividad reflejan la vista pública consultada y son orientativas. Para integrar las opciones que exponen stdio, Codex y Claude necesitan el comando y los argumentos correspondientes. Los instaladores de algunos proyectos también escriben configuración de cliente.

| Proyecto | Arquitectura, instalación y mantenimiento | Evidencia y decisión |
|---|---|---|
| [Creative Editor](https://github.com/Anujpal-15th/resolve-creative-editor-mcp) | Python 3.10, Lua y archivos. FFmpeg para análisis, motor Studio opcional. MIT, historial inicial de 7 commits. | El mantenedor publica 23 comprobaciones en Windows Free 21.1.0.17. Buen referente para lectura, colocación, recorte, movimientos y operaciones de audio. En el receptor se revisó la ruta de comandos por archivo ejecutable. Se conservaron el patrón de lectura posterior y la prueba sintética como referencia. [Receptor Lua](https://raw.githubusercontent.com/Anujpal-15th/resolve-creative-editor-mcp/main/resolve_bridge.lua) |
| [AI Bridge](https://github.com/flamexnreal/davinci-resolve-ai-bridge-mcp) | Python y Lua, IPC nativo por archivos, mensajes firmados. Instaladores de Windows/macOS y pruebas con dobles de Resolve. MIT, publicaciones y seguimiento de incidencias. | La matriz publica pruebas en macOS Free 21.1.2.10. Un issue de Windows en esa compilación describe contención del archivo de entrada. Se verificó localmente el mismo mecanismo nativo con despacho puntual y operaciones fijas. [Compatibilidad](https://github.com/flamexnreal/davinci-resolve-ai-bridge-mcp/blob/main/docs/COMPATIBILITY.md) · [Fuente de la API de archivos](https://raw.githubusercontent.com/flamexnreal/davinci-resolve-ai-bridge-mcp/main/agent/ResolveLua.lua) · [Issue 6](https://github.com/flamexnreal/davinci-resolve-ai-bridge-mcp/issues/6) |
| [Resolve Pilot](https://github.com/emircbngl/davinci-resolve-mcp-free) | Python 3.11+, FFmpeg, Lua, FCPXML y SRT. UI por accesibilidad en macOS. MIT, 48 commits visibles y pruebas con mocks Lua e integración MCP. | Prueba publicada en Free 20.3, reporte de consola en 21.1.1. El camino Lua documentado depende de funciones que faltan en compilaciones posteriores y admite ejecución Lua general. El commit de exportadores indicado en el plan no se pudo abrir en el visor web durante la auditoría. Se implementó FCPXML con la referencia de Apple. |
| [hiteshK03](https://github.com/hiteshK03/davinci-resolve-mcp) | Puente Python dentro de Resolve, HTTP local, servidor MCP y dependencias opcionales de IA. MIT, 4 commits y un issue visibles. | Ofrece edición, gestión y transcripción. El arranque mediante scripts Python limita la evidencia en Free 21.1. El diseño HTTP original carece de la restricción de origen añadida por EddieRivers. |
| [MDizzleZA](https://github.com/MDizzleZA/davinci-resolve-mcp-free) | Fork de hiteshK03. Instalador Windows, trabajos asíncronos, handshake y herramientas agrupadas. MIT, 2 commits visibles. | Las pruebas cubren transporte y enrutamiento. Hereda el arranque Python dentro de Resolve. La agrupación simplifica el catálogo MCP. |
| [EddieRivers](https://github.com/EddieRivers/davinci-resolve-mcp-free) | Fork de hiteshK03 fijado por su mantenedor a `f812df7`. HTTP en loopback, filtros de Origin y Host, extras de IA opcionales. MIT, 6 commits visibles. | Mejora el perímetro HTTP. Comparte la dependencia del arranque Python y carece de una validación publicada para la compilación objetivo. |
| [allensandiego](https://github.com/allensandiego/davinci-resolve-mcp) | Implementación Lua más cliente Python, buzón de archivos y operaciones fijas. Instalación con uv y pruebas pytest con fuscript. MIT, 14 commits visibles. | Expone estado, timelines, marcadores y gestión de proyectos. El directorio temporal por defecto requiere revisión de permisos para un despliegue multiusuario. Las pruebas publicadas no acreditan la compilación objetivo. |
| [saadk408](https://github.com/saadk408/davinci-resolve-lua-mcp) | Node 20, Lua, archivos de solicitud y respuestas en preferencias de Fusion. MIT, 65 commits y 6 issues visibles. | Publica comprobaciones sobre 21.1.0.17 y deja Windows como experimental. Su diseño de preferencias persistentes y su ruta de archivos ejecutables aumentan la superficie frente a un buzón privado de datos. [Notas de arquitectura](https://github.com/saadk408/davinci-resolve-lua-mcp/blob/main/CLAUDE.md) |
| [samuelgursky](https://github.com/samuelgursky/davinci-resolve-mcp) | Proyecto de origen de la familia hiteshK03, Python y API oficial Studio, puente Python en la aplicación y motor Node opcional. MIT, historial amplio y política de seguridad publicada. | Free 21.0.x dispone de evidencia en macOS y reportes Windows/Linux. El menú Python en Free 21.1 tiene un reporte de ausencia. Referencia de API y compatibilidad histórica. |
| [Aedelon](https://github.com/Aedelon/davinci-mcp) | Python con acciones tipadas, lectura posterior, confirmación de borrado, registro y snapshots. Apache-2.0, 52 commits visibles, suite de tests. | Su vía Studio o Python antiguo queda fuera del objetivo. Su experiencia con el sandbox 21.1.2 debe leerse junto a la prueba publicada de AI Bridge con archivos Fusion en esa misma familia. Sus protecciones de escritura sirven como referencia. |

La selección prioriza evidencia en la compilación objetivo, escrituras acotadas y facilidad de prueba. Se implementó un servidor pequeño que mantiene el diseño del plan, con MCP por stdio, validación de un catálogo local y operaciones fijas dentro de Lua. El protocolo de buzón y el exportador son propios. La revisión del código de Creative Editor y AI Bridge se centró en las interfaces relevantes al flujo vertical. La auditoría de dependencias y el historial completo de cada candidato quedan pendientes para cualquier decisión futura de incorporar código. [Transporte MCP](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports) · [Temporización y medios FCPXML](https://developer.apple.com/documentation/professional-video-applications/asset-clip)

## Operaciones y evidencia

| Operación | Mecanismo y estado | Precisión y riesgo |
|---|---|---|
| Detectar edición/compilación, consultar proyecto y enumerar timelines | Lua + MCP, probado en dos proyectos de la biblioteca desechable. | Consulta. Los IDs salen de Resolve y las escrituras se vinculan a ellos. |
| Crear marcador | Lua + MCP, probado en A en 120, con lectura posterior y persistencia tras reabrir. Segunda solicitud con otro ID sobre el mismo fotograma rechazada. | Entero relativo al inicio de timeline. Escritura limitada a biblioteca y proyecto armados por el operador. |
| Montar B–A–C | FCPXML 1.9 importado por menú en A y por `ImportTimelineFromFile` mediante el buzón MCP en B. Probado con 30 fps y material sintético con audio mono. | V1 y A1, cortes 120/210, duración de 360 fotogramas. El receptor verifica ruta, origen, inicio y duración de cada segmento. |
| Importar medios y gestionar proyectos | La importación FCPXML incluyó medios de origen. Crear, guardar, cerrar y reabrir proyectos funcionó desde la consola Lua de prueba. | Las operaciones de gestión del proyecto se hicieron fuera del catálogo MCP, durante la validación. |
| Mover, recortar o dividir clips existentes, editar por pista, eliminar | El mantenedor de Creative Editor aporta evidencia para algunas operaciones de reconstrucción en Windows. Pendiente como herramienta MCPX-Free. | Cambios sobre clips existentes requieren inspeccionar atributos, transiciones, vínculos, velocidad y recuperación. El ensamblado actual aplica cortes en una timeline nueva. |
| EDL, AAF, OTIO | La declaración `ImportTimelineFromFile` del SDK instalado enumera estos formatos. Se seleccionó FCPXML para probar rangos y conservar AV del mismo archivo. | Pendiente medir semántica y fidelidad de pistas por formato. |
| UI y teclado | Importación manual comprobada. La UI se utilizó para abrir Resolve y lanzar la consola. | Los menús pueden servir de alternativa. El montaje usa archivo y API, con verificación de estado. |
| FFmpeg, subtítulos y análisis externo | Los medios sintéticos se generaron con PyAV/NumPy ya presentes. Quedan por evaluar el script de subtítulos del usuario, FFmpeg como proceso externo, transcripción, análisis y render. | Un archivo generado y su presentación final necesitan verificaciones distintas. La sincronía medida hasta ahora corresponde a los rangos de los elementos en la timeline. |

En la prueba B, un segundo despacho del mismo ID recuperó la misma timeline. Tras guardar, cerrar y reabrir, se encontró una sola timeline con ese ID, 360 fotogramas y tres elementos por pista de video y audio. Cada clip de video devolvió un elemento vinculado. El cabezal confirmó B → A al pasar de 03:29 a 04:00 y A → C de 06:29 a 07:00. Se leyeron los inicios de origen 60, 30 y 0. En la lectura del proyecto A, `GetSourceEndFrame` devolvió 179, 120 y 150. Se validó con origen inicial, extensión de timeline y duración, pues esa lectura final no mostró una convención uniforme al llegar al último fotograma del archivo. Quedan pendientes el análisis de píxeles y de señal de audio renderizada, FPS fraccionarios o mixtos, varias pistas, timecode no cero en el montaje Lua y medios habituales.

El proceso local de Codex descubrió el catálogo de inspección y marcador mediante una configuración temporal. El cliente MCP de prueba invocó la edición y la lectura reales. Quedan pendientes la invocación de montaje desde una conversación de Codex y las pruebas con Claude Code y Claude Desktop. La integración Lua en otras compilaciones, incluido el arranque mediante `fusion:RunScript`, requiere repetir las pruebas por compilación. Las pruebas Python distinguen el transporte real stdio de las respuestas simuladas del buzón.
# Revisión de puesta en marcha · 20 de noviembre de 2026

**Decisión.** Se puede abrir un piloto con medios sintéticos en la biblioteca desechable de Windows. Esta revisión ejecutó seis pruebas unitarias, la simulación Python/Lua y dos consultas de solo lectura por MCP stdio contra Resolve Free 21.1.0.17. Las escrituras y la reapertura descritas más abajo corresponden a ensayos anteriores.

| Comprobación | Resultado observado |
|---|---|
| `python -m unittest -v` y `python simulate.py` | Seis pruebas aprobadas y simulación terminada con código 0. Incluye montaje, repetición del ID, fallos de verificación, colisión de marcador y cambio de proyecto. |
| `request_inspection` | Respondió el receptor de la sesión privada. Proyecto activo `MCPX-TEST-B`, timeline activa identificada mediante su ID. |
| `request_timeline` | V1 y A1 devolvieron B [0,120), A [120,210), C [210,360), con orígenes 60, 30 y 0. A 30 fps son 12 segundos. El análisis de Creative Editor contó cero huecos y cero solapamientos. |

**Hallazgos abiertos.** En `live.py`, el lector exige un salto de línea dentro de los primeros 262 144 bytes. Por inspección del código, una respuesta mayor parece pendiente hasta vencer. Falta reproducir ese límite con una timeline extensa y devolver un error explícito o paginar. En `worker.lua`, la última cabecera procesada se conserva en memoria. Un reinicio puede volver a despachar la solicitud vigente. La simulación comprueba la repetición, pero falta interrumpir una importación real y verificar la recuperación. El estado inicial `pending_operator` por sí solo tampoco confirma que el receptor esté activo. Para comprobarlo hay que obtener `read_from_resolve`.

## Contraste con los siete criterios del documento original

Revisión del 20 de noviembre en la sesión de Windows. Se repitieron las seis pruebas Python, la simulación Lua y dos consultas de solo lectura a Resolve.

| Criterio | Estado | Evidencia y alcance |
|---|---|---|
| 1. Comunicación con un agente | Parcial | Codex descubrió herramientas en una configuración temporal. El cliente de prueba negoció MCP, enumeró nueve herramientas e invocó dos consultas. Falta una edición solicitada desde un chat de Codex o Claude. |
| 2. Identificación del entorno | Cumplido en este equipo | Resolve respondió con edición Free y compilación 21.1.0.17. |
| 3. Consulta de un proyecto real | Cumplido | Se leyó MCPX-TEST-B, el ID de su timeline activa y los seis elementos de V1/A1. |
| 4. Modificación de timeline | Cumplido en la biblioteca desechable | Ensayos anteriores verificaron un marcador y la importación B–A–C como timeline nueva. |
| 5. Verificación independiente del comando | Cumplido para la estructura | Una consulta posterior leyó orden, pistas y cortes en 120/210. Un montaje anterior sobrevivió a la reapertura. Queda por inspeccionar la imagen y el sonido del render. |
| 6. Errores y capacidades | Parcial | El simulador cubre rechazos de escritura. En un buzón temporal una respuesta completa de 262 144 bytes se interpretó correctamente y otra de 262 146 apareció como pendiente. La desconexión tampoco tiene un estado propio. |
| 7. Instalación reproducible | Parcial | Hay instrucciones y pruebas repetibles en este equipo. Falta arrancar desde cero en otro entorno Windows y validar cada cliente anunciado. |

El hito de montaje del primer día tiene evidencia. La primera versión en vivo sigue pendiente de aceptación desde el cliente conversacional. Los hitos de video habitual subtitulado y distribución pública siguen abiertos.


## Preparación para compartir el código

Se añadieron licencia MIT para el código propio, créditos de las tres fuentes
principales y un arranque con rutas derivadas de la copia descargada. El aviso
original de Creative Editor se conserva completo. Los directorios de pruebas,
medios generados, sesiones y configuración local quedan excluidos por gitignore.

El fallo de respuestas grandes descrito en esta auditoría se corrigió para
devolver un error explícito al superar 256 KiB. Pasaron siete pruebas Python,
incluida la regresión que comprueba ese error y que el servidor continúa
respondiendo. La paginación, el render y la instalación en otro Windows siguen
pendientes. La publicación prevista corresponde a una versión experimental.

## Panel local de activación

Se añadió launcher.pyw con estado del receptor, control de desconexión y
generación de una entrada Lua para el menú Scripts de Resolve. El instalador
apunta a la sesión elegida y restringe el arranque a proyectos MCPX-TEST.
La ventana se inspeccionó visualmente con la altura corregida para mostrar
todos sus controles. Pasaron ocho pruebas Python y la simulación Lua extendida
para parada y reconexión. Se corrigió el reconocimiento de stop con CRLF en
Windows. El operador confirmó la activación desde el menú en Resolve Free 21.1.0.17.
Una consulta MCP posterior devolvió el proyecto de prueba y la timeline esperados.
El círculo del panel detuvo el receptor y este escribió el estado stopped. La ventana usa Python y Tkinter. El empaquetado como exe autónomo
sigue pendiente.

El arranque por menú reveló que los scripts no compartían las variables globales
establecidas por el activador. Se corrigió el paso de configuración mediante
Fusion SetData/GetData, conservando el arranque por consola. La simulación
comprueba ahora una operación de marcador con esas variables globales ausentes.
El acceso directo local MCPX Free.lnk abre el panel con pythonw. Ese acceso
contiene rutas del equipo y queda excluido de Git.
