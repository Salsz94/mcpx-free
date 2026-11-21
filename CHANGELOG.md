# Historial de cambios

Cada entrega publicada tendrá una etiqueta Git y una release de GitHub.
`v1.1.0` corresponde a la entrega 1.1. Las correcciones incrementan el último
número, como `v1.1.1`. Las nuevas funciones incrementan el segundo, como
`v1.2.0`. Los cambios incompatibles incrementan el primero.

La etiqueta identifica el código de cada entrega. Las notas registran mejoras,
pruebas y límites conocidos. El carácter experimental se conserva mientras
continúen pendientes la autorización del panel y la instalación en otro equipo.

## v1.1.0 — 21 de noviembre de 2026

Primera entrega etiquetada. Base de comparación anterior sin etiqueta
`d2949ea`, que ya incluía el panel, la reconexión y el montaje por beats.

### Mejoras

- Limpieza experimental de locución desde MCP con transcripción local,
  detección de pausas y revisión de repeticiones. Permite elegir otra toma o
  conservar las alternativas.
- Construcción por lotes de clips de audio editables enlazados al medio original,
  en una pista nueva silenciada, con verificación antes de activarla.
- Lectura de audio en páginas de 40 clips y recuperación de trabajos parciales
  mediante su identificador.
- Auditoría reproducible con operaciones fijas en proyectos de pruebas y
  registro de todos los intentos y del último resultado por caso.
- Identificación de versión en el servidor MCP y mediante `--version`.

### Correcciones

- El umbral de silencio también configura el detector de voz para separar
  frases repetidas con pausas breves.
- Calibración del fotograma final de audio, incluido el caso de un solo fotograma.
- Recuperación de la configuración del último clip tras fallar una propiedad.
- Lectura posterior de propiedades y fundidos, contemplando la limitación de
  los fundidos en clips de uno o dos fotogramas.
- Normalización de saltos de línea en las sondas de selección y render.
- Reintentos acotados ante bloqueos breves de archivos en Windows.

### Validación

- 21 casos reales con último resultado aprobado después de corregir y repetir
  los casos afectados, en Resolve Free 21.1.0.17 y Windows.
- Montaje de 12 segundos con 24 tomas y cortes en los 23 beats interiores.
- Limpieza controlada de voz de 13,7 a 5,8667 segundos.
- 400 fragmentos de audio con rangos y posiciones verificados, diez páginas
  de lectura y repetición sin duplicar la pista.
- LUT con cambio medido en píxeles y render corto MP4 con video y audio
  decodificables.
- 12 pruebas automatizadas y simulación Python/Lua aprobadas.

El alcance y los errores de los intentos anteriores están registrados en
[PRUEBAS_REALES.md](PRUEBAS_REALES.md).

### Límites conocidos

- Las escrituras en proyectos habituales necesitan autorización acotada; falta
  incorporarla al panel.
- Color, títulos, Fusion, transformaciones, velocidad y render se probaron con
  sondas técnicas. Faltan herramientas MCP generales para esas operaciones.
- La selección visual y el arranque del detector de beats requieren preparación
  local del agente. La limpieza de voz requiere Whisper base descargado.
- Los lotes extensos necesitan mejoras de rendimiento. Otras versiones de
  Resolve, clientes MCP y equipos Windows siguen pendientes de prueba.

## Siguientes entregas previstas

- 1.2: revisión y autorización desde el panel para limpiar una timeline habitual.
- Entregas posteriores: herramientas generales de efectos y render, integración
  de los flujos de beats y selección, progreso y optimización de lotes.

Estas líneas son prioridades de desarrollo; cada release indicará qué quedó
implementado y probado.
