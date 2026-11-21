# Pruebas reales de MCPX-Free

Registro cerrado el 21 de noviembre de 2026. **21 casos con último resultado
aprobado**, después de corregir fallos y repetir los casos afectados. El informe
conserva 52 registros de ejecución, incluidos 18 errores de intentos anteriores
y sus dependencias. La batería automatizada adicional aprobó 12 pruebas y la
simulación Python/Lua terminó con código cero.

## Entorno y método

Windows, DaVinci Resolve **Free 21.1.0.17**, Python **3.10.11 de 64 bits**,
biblioteca desechable MCPX Scratch y proyecto MCPX-TEST-B. Se recuperó la
conexión con la biblioteca existente y se abrió el proyecto antes de ejecutar
las escrituras. El receptor se activó desde Workspace → Scripts → MCPX Free.

Dependencias locales observadas: PyAV 17.1.0, NumPy 2.2.6, faster-whisper 1.2.1,
CTranslate2 4.9.0 y librosa 0.11.0. La transcripción usó Whisper base, CPU e int8.

El cliente `smoke.Client` negoció MCP por stdio con el servidor de esta copia.
Las solicitudes cruzaron el buzón y se ejecutaron dentro del Resolve abierto.
`audit.py` registra cada intento y obtiene lecturas posteriores. Las operaciones
de `audit_probe.lua` son fijas y están limitadas al proyecto de pruebas armado.
La solicitud contiene datos y el nombre de una operación predefinida.

El material visual procede de una selección anterior del agente sobre videos
reales de productos, normalizados a vertical y 30 fps. La auditoría reutilizó
esa selección y el análisis obtenido previamente con el motor local del
BeatDetector del operador. El ensayo de voz usó una frase duplicada, con una
pausa conocida de 1,2 segundos y márgenes de silencio.

## Resultados

MCP indica un flujo disponible mediante herramientas del servidor. Agente + MCP
incluye análisis o preparación local del agente. Sonda API indica una operación
técnica fija que atraviesa el puente y que todavía requiere una herramienta
general para el uso editorial habitual. Todos los casos siguientes terminaron
aprobados dentro del alcance de su comprobación.

| Nº | Prueba | Resultado medido | Acceso actual |
|---|---|---|---|
| 01 | Conexión y entorno | Free 21.1.0.17, proyecto e IDs vigentes | MCP |
| 02 | Montaje de tomas seleccionadas previamente | Ocho tomas de producto, 12 segundos, V1/A1 | Agente + MCP |
| 03 | Cambio de toma en cada beat | 24 tomas, 23 cortes coincidentes con todas las marcas interiores | Detector local + agente + MCP |
| 04 | Duraciones uniformes | 12 clips de 30 fotogramas, 12 segundos | Agente + MCP |
| 05 | Reordenación y rangos | Tres medios en orden inverso, entrada de origen en fotograma 2 | MCP |
| 06 | Zoom, posición y rotación | Zoom 1,15, paneo 24 y rotación 3 leídos de vuelta | Sonda API |
| 07 | Velocidad | 80 % leído de vuelta, sin ripple; duración de 18 fotogramas mantenida | Sonda API |
| 08 | Volumen y paneo de audio | −6 dB y paneo 15 leídos de vuelta | Sonda API |
| 09 | Fundidos de audio | Entrada y salida de tres fotogramas leídas de vuelta | Sonda API |
| 10 | Efecto Fusion | Composición con un Glow entre MediaIn y MediaOut | Sonda API |
| 11 | Color mediante LUT instalado | LUT leído y cambio RGB medido en el render | Sonda API |
| 12 | Título Text+ editable | Elemento insertado y texto MCPX AUDIT leído desde su composición | Sonda API |
| 13 | Render corto de video y audio | MP4 H.264, 15 imágenes y 24 576 muestras de audio decodificadas; Complete 100 % | Sonda API |
| 14 | Silencios y repetición exacta | Dos repeticiones reconocidas; 13,7 s de entrada y 5,8667 s conservados | MCP + Whisper local |
| 15 | Voz editable desde el original | Un segmento de 176 fotogramas en pista nueva silenciada; medio original y respaldo comprobados | MCP |
| 16 | Activación tras verificar | A2 activa y A1 silenciada, estado leído de vuelta | MCP |
| 17 | Carga y recuperación de 400 segmentos | Duraciones de 1–5 fotogramas, diez páginas, cero diferencias de tiempo; repetición sin otra pista | MCP |
| 18 | Timeline incorrecta | Solicitud rechazada y timeline activa conservada | MCP |
| 19 | Guardar y reabrir | Mismo ID de timeline encontrado al guardar, cerrar y cargar el proyecto | Sonda API |
| 20 | Elegir la toma desde Codex | Primera 5,5 s, ambas 11,5 s o última 5,8667 s | MCP |
| 21 | Clip de origen inexistente | Plan rechazado antes de crear una pista; cantidad y estados de pistas conservados | MCP |

La comparación de color usó el mismo montaje antes y después del LUT. La suma
de diferencias de las medias RGB fue 69,6784 en un fotograma decodificado. Esto
acredita un cambio de imagen, sin valorar su calidad estética. Los casos 06–10
y 12 verifican valores o estructura mediante API; su evaluación visual o auditiva
completa queda para el encargo editorial.

La prueba 17 se recuperó sobre la misma pista de un intento interrumpido.
La fase final de continuación y verificación duró 205,12 segundos. Los lotes
iniciales de 25 clips tardaron aproximadamente 25–30 segundos cada uno en este
equipo. Ese tiempo final no representa construir 400 clips desde cero.

El proyecto quedó guardado con la timeline de voz controlada
`MCPX AUDIT Audio 6f0a8c3e 1795275229` abierta, A1 silenciada y A2 activa.
La timeline de beats es `MCPX-b80dd80c67d24ab0adccf23cf1f78283`.

## Errores encontrados y tratamiento

- La importación tipada `ImportMedia({{FilePath=...}})` devolvió un resultado
  vacío en esta instalación. La prueba usa la alternativa de lista de rutas
  cuando esa forma no devuelve medios.
- Cambiar el FPS de una timeline recién creada puede devolver falso si ya
  tiene ese valor. La prueba lee primero el FPS y activa ajustes propios
  cuando debe cambiarlo. Los nombres de timelines de ensayo incluyen una marca
  temporal para permitir repetir casos.
- La sonda pasaba al render un ID con salto de línea conservado por `ReadLine`.
  Ocurrió lo mismo al seleccionar una timeline por nombre. Se normalizó el final
  de esas líneas. El último render devolvió `Complete` y 100 %. La comprobación
  también exige existencia y decodificación del archivo resultante. Un render
  detenido por sí solo no acredita éxito.
- Un LUT arbitrario en la carpeta de sesión fue rechazado. El SDK instalado
  exige que Resolve haya descubierto el LUT. El ensayo de color se repite con
  un LUT instalado y una comparación de píxeles renderizados.
- La configuración inicial del detector de voz conservaba una pausa de
  1,2 segundos dentro de una sola frase. El umbral solicitado de silencio ahora
  configura también el VAD. La aceptación exige detectar las dos repeticiones
  y conservar una sola, además de obtener una transcripción.
- `AppendToTimeline` de audio utiliza un final exclusivo en esta compilación.
  La construcción calibra la convención y recupera el caso de un solo fotograma,
  cuya solicitud con entrada y salida iguales devuelve cero elementos.
- Copiar todas las propiedades de audio puede fallar durante un lote largo.
  Se escriben las propiedades distintas, se leen de vuelta y se permite
  completar la configuración del último clip tras una interrupción.
- Resolve aceptó fundidos solapados en clips de dos fotogramas y devolvió
  valores recortados. Los clips de uno o dos fotogramas conservan fundidos cero.
  A partir de tres se comprueban ambos fundidos de un fotograma, con tolerancia
  para pequeños residuos numéricos de la API.

Los intentos fallidos permanecen en el informe privado. Los borradores parciales
se conservaron en el proyecto de pruebas para inspección y recuperación.

## Alcance práctico

El agente puede decidir rangos a partir de un encargo editorial y entregar al
puente un plan. La selección visual necesita imágenes, criterio editorial y
preparación local del material. En este flujo los clips visuales apuntan a los
medios preparados. Conservar el plan y los originales permite generar otros
rangos. La limpieza de voz sí coloca fragmentos enlazados al archivo original.

Las repeticiones textuales exactas y con confianza suficiente se preseleccionan
conservando la última. Las variantes similares quedan disponibles para elegir
con `choose_take`. La calidad de una interpretación, una toma desenfocada o un
gesto apropiado requieren análisis y revisión. La lectura estructural tampoco
sustituye escuchar los cortes antes de entregar una locución.

El montaje por beats admite análisis local y colocación de marcas mediante MCP.
La auditoría construye la lista de tomas para cubrir cada intervalo entre beats.
El arranque del detector y la preparación visual siguen siendo pasos del agente
fuera del catálogo MCP. Los efectos, títulos, color, velocidad y render se
ejercitan mediante sondas de auditoría. Falta exponerlos como herramientas
generales con su validación, previsualización y recuperación.

La limpieza implementada admite audio mono o estéreo, sin solapamientos y a
velocidad 100 %, con un máximo de 2000 segmentos. Se construye en lotes de 25
en una pista silenciada. El rendimiento de lotes grandes sigue siendo una
limitación. Los proyectos habituales necesitan un permiso acotado a IDs y
trabajo. El panel todavía carece de una interfaz para concederlo.

Quedan sin probar FPS fraccionarios en Resolve real, canales surround, medios
offline, multicámara, transiciones complejas, rampas de velocidad, instalación
en otro Windows y otros clientes MCP. La sincronización de AV del montaje se
comprueba por rangos en la timeline. El ensayo corto de render comprueba que
el archivo contiene video y audio decodificables.

## Siguiente desarrollo

1. Añadir al panel la revisión del resumen y la autorización de un trabajo
   sobre un proyecto habitual. Mostrar timeline, pista, duración y descartes
   previstos antes de construir la pista de limpieza.
2. Unificar análisis, revisión y montaje en flujos de alto nivel para Codex.
   Integrar un adaptador del motor local de BeatDetector y una salida de rangos
   del script externo Limpiar Tomas. El código privado del operador permanece
   fuera de la distribución.
3. Convertir las sondas aprobadas de transformaciones, color, títulos, Fusion,
   velocidad y render en herramientas MCP con argumentos limitados y lectura
   posterior. Añadir selección explícita de clips y destinos.
4. Optimizar lotes extensos, informar de su progreso, incorporar cancelación y
   probar de nuevo la recuperación. Mantener una paginación completa de audio
   y ampliar la paginación a la inspección general de timelines.
5. Medir minutos ahorrados y correcciones en encargos completos. Repetir con
   FPS mezclados, audio separado, otro Windows y los clientes anunciados antes
   de ampliar la compatibilidad declarada.

## Repetición y evidencias

`audit.py` necesita Resolve abierto, un proyecto de pruebas armado y tres
entradas locales: catálogo visual preparado, análisis de beats y WAV de voz
controlada con una frase de unos 5–6 segundos repetida dos veces. Las pruebas
de voz esperan una sola repetición descartada y una salida de entre 5 y 7 segundos.

```powershell
python audit.py --session RUTA_SESION --fixture RUTA_CATALOGO --beats RUTA_BEATS_JSON --voice RUTA_WAV_CONTROLADO
python -m unittest -v
python simulate.py
```

Los resultados detallados se guardan bajo `SESION/audit-ID/report.json`, junto
con los logs y renders. `results` conserva los intentos, `latest_results` muestra
el último resultado por caso y `source_sha256_at_report` identifica los archivos
de código al escribir el informe. Las sesiones, medios, transcripciones y rutas
personales permanecen en directorios ignorados por Git.

Las pruebas unitarias y la simulación usan datos u objetos de prueba. Se
registran por separado de las operaciones ejecutadas dentro de Resolve.

La sesión local de esta ejecución es
`.scratch/private-ipc/audit-6f0a8c3ef2944e0ebd0a13deed643fa2/report.json`.
Ese archivo privado contiene los rangos, IDs y rutas que permiten revisar
cada intento. Este documento contiene el resumen apto para revisión del proyecto.
