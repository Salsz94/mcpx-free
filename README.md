# MCPX-Free

Puente experimental para Windows. Se comprobó el montaje desde una conversación
de Codex en Resolve Free 21.1.0.17, con Python 3.10 de 64 bits y medios
sintéticos a 30 fps. El usuario confirmó la lectura del montaje después de
reabrir el proyecto. Siguen pendientes Claude, el render y los medios habituales.

## Panel y activación desde el menú

Abra `launcher.pyw` con Python para mostrar el panel de escritorio. En la copia
de desarrollo usa la sesión `.scratch/private-ipc`. Para otra sesión, inicie
`pythonw launcher.pyw --session "C:\ruta\sesion"` o elija Cambiar sesión.

Pulse **Preparar botón en Resolve** una vez. Esto instala el script
`MCPX Free.lua` en los scripts Utility de su cuenta de Windows, apuntando a la
copia y sesión elegidas. Si mueve el proyecto o cambia de sesión, vuelva a
preparar el botón. El cliente MCP debe seguir apuntando a esa misma sesión.

En Resolve, abra un proyecto de pruebas `MCPX-TEST-…` y seleccione
**Workspace → Scripts → MCPX Free**. El nombre de la biblioteca y del proyecto
se toman del proyecto de pruebas abierto. Al reiniciar Resolve seleccione de
nuevo la entrada. Según la versión, un script recién instalado puede requerir
reabrir el menú o reiniciar Resolve para aparecer.

El panel pasa a **Puente activado** cuando recibe una señal reciente del
receptor. Pulse el símbolo de encendido para desconectarlo. Con el receptor
desconectado, el símbolo muestra el paso de activación en el menú de Resolve.
Cerrar el panel deja el receptor en el estado en que se encontraba.

El estado comprueba el receptor Lua. La consulta `request_inspection` seguida
de `resolve_result` comprueba además el recorrido MCP hasta el proyecto.
Para desinstalar la entrada, elimine únicamente `MCPX Free.lua` de
`%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility`.


## Arranque desde una copia descargada

Descargue y extraiga el proyecto o clone su repositorio. Abra PowerShell en la
carpeta que contiene `server.py`. Necesita Python 3.10 de 64 bits y Resolve Free.
El servidor usa la biblioteca estándar. El siguiente bloque instala PyAV y NumPy
en un entorno local para generar medios de demostración.

```powershell
python -m venv .venv
$python = (Resolve-Path .\.venv\Scripts\python.exe).Path
& $python -m pip install av numpy
& $python -m unittest -v
& $python make_fixture.py .scratch-fixture
$repo = (Get-Location).Path
$fixture = (Resolve-Path .\.scratch-fixture).Path
$session = Join-Path $env:LOCALAPPDATA ('MCPX-' + [guid]::NewGuid().ToString('N'))
.\new-session.ps1 -Path $session
```

La carpeta de demostración debe ser nueva al generarla. Para repetir, conserve
el catálogo existente o elija otra carpeta. Si PowerShell bloquea el script de
sesión, revise la política aplicable en su equipo.

En Resolve cree una biblioteca desechable `MCPX Scratch` y el proyecto
`MCPX-TEST-A`. Este bloque imprime la línea Lua con las rutas de su copia.
Péguela en **Workspace → Console**, en modo Lua.

```powershell
$luaRepo = $repo.Replace('\', '/')
$luaSession = $session.Replace('\', '/')
'MCPX_DIRECTORY="' + $luaSession + '"; MCPX_TEST_LIBRARY="MCPX Scratch"; MCPX_TEST_PROJECT="MCPX-TEST-A"; MCPX_BRIDGE_SCRIPT="' + $luaRepo + '/bridge.lua"; dofile("' + $luaRepo + '/worker.lua")'
```

Debe aparecer `MCPX worker running`. Mantenga Resolve abierto. Desde la misma
PowerShell puede probar la conexión antes de registrar un cliente.

```powershell
& $python smoke.py --session $session request_inspection
```

Copie el `request_id`, espere un momento y consulte el resultado.

```powershell
$requestId = Read-Host 'Pegue el request_id'
$requestArgs = '{"request_id":"' + $requestId + '"}'
& $python smoke.py --session $session resolve_result $requestArgs
```

La respuesta esperada es `read_from_resolve`. Si devuelve `pending_operator`,
consulte el mismo ID y compruebe que el receptor siga activo. El receptor y el
cliente deben usar la misma carpeta de sesión. Al crear otra sesión actualice
ambos extremos.

Servidor MCP local para preparar montajes y verificarlos en DaVinci Resolve Free para Windows. El caso comprobado usa Resolve **21.1.0.17**, Python 3.10 y material sintético. El servidor usa la biblioteca estándar de Python. Resolve procesa cada solicitud cuando el operador ejecuta el receptor desde su consola Lua.

El puente también dispone de modo continuo, comprobado en Free 21.1.0.17. Con las variables de sesión, biblioteca y proyecto de prueba configuradas, ejecute una vez por sesión:

```lua
MCPX_BRIDGE_SCRIPT="D:/ruta/mcpx-free/bridge.lua"; dofile("D:/ruta/mcpx-free/worker.lua")
```

Mientras ese script esté activo, procesa las solicitudes del servidor. El estado inicial `pending_operator` indica que están en cola y `resolve_result` permite leer el resultado al terminar. Para detenerlo, ejecute en la consola `fusion:SetData("MCPX.WorkerOwner", nil)`. El modo continuo requiere `dofile` y `bmd.wait`. La compatibilidad con otras compilaciones queda pendiente.

La herramienta `request_timeline` obtiene los clips con sus pistas y rangos. Su resultado incorpora el análisis de huecos y solapamientos reutilizado de Creative Editor. Consulte la procedencia y la licencia en [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Preparación en Windows

1. Abra PowerShell en la carpeta del proyecto. Ejecute `python -m unittest -v` para comprobar el servidor y el exportador.
2. Cree una biblioteca local desechable en Resolve y un proyecto con nombre como `MCPX-TEST-A`. Use medios copiados o sintéticos.
3. Cree una carpeta de sesión nueva en un disco local NTFS. El script restringe y verifica la ACL antes de habilitar sus archivos.

   ```powershell
   $session = Join-Path $env:LOCALAPPDATA ('MCPX-' + [guid]::NewGuid().ToString('N'))
   .\new-session.ps1 -Path $session
   ```

4. Prepare el catálogo local. Cada medio necesita una ruta relativa a la raíz de medios, su número de fotogramas y el número de canales de audio. Verifique esos datos con su herramienta de inspección de medios. Esta versión usa video CFR con FPS enteros y resolución homogénea, audio a 48 kHz, y cero, uno o dos canales por archivo. Use clips con origen cero para el montaje por Lua.

   ```json
   {
     "fps": 30,
     "width": 320,
     "height": 240,
     "media": {
       "A": {"file": "A sample.mov", "frames": 180, "audio_channels": 1},
       "B": {"file": "B sample.mov", "frames": 180, "audio_channels": 1},
       "C": {"file": "C sample.mov", "frames": 180, "audio_channels": 1}
     }
   }
   ```

   Si PyAV y NumPy ya están disponibles, `python make_fixture.py .scratch-fixture` genera el catálogo y tres clips de prueba con barras móviles y tonos diferenciados. Cree un directorio de salida dedicado. Para inspección y marcadores basta `--session`. Para un servidor dedicado a FCPXML puede omitir `--session`.

## Cliente MCP

Use rutas absolutas y el ejecutable Python de su cuenta. Sustituya las rutas de ejemplo antes de registrar el servidor. [Codex MCP](https://developers.openai.com/codex/mcp) · [Claude Code MCP](https://code.claude.com/docs/en/mcp)

```powershell
$python = (Resolve-Path .\.venv\Scripts\python.exe).Path
$server = (Resolve-Path .\server.py).Path
$fixture = (Resolve-Path .\.scratch-fixture).Path
$serverArgs = @($server, '--session', $session, '--media-root', "$fixture\media",
                '--manifest', "$fixture\manifest.json", '--output', "$fixture\output")
codex mcp add mcpx-free -- $python @serverArgs
claude mcp add --transport stdio mcpx-free -- $python @serverArgs
```

Si PowerShell indica que `codex` no se reconoce y usa Codex Desktop de Microsoft
Store, localice el ejecutable instalado. Use las variables del bloque anterior.

```powershell
$codexPackage = Get-AppxPackage -Name OpenAI.Codex
if (!$codexPackage) { throw 'No se encontró Codex Desktop. Revise la instalación de su cliente MCP.' }
$codexExe = Join-Path $codexPackage.InstallLocation 'app\resources\codex.exe'
& $codexExe mcp add mcpx-free -- $python @serverArgs
```

En Claude Desktop use una entrada `mcpServers.mcpx-free` con `command` igual al ejecutable y `args` igual a la lista anterior. Reinicie el cliente tras registrar el servidor. Para desregistrar use `codex mcp remove mcpx-free` o `claude mcp remove mcpx-free`, según corresponda.

## Consulta y edición

1. Llame a `request_inspection`. El servidor devuelve `pending_operator` y un `request_id`.
2. Abra **Workspace → Console** en Resolve. Ejecute la línea Lua siguiente con sus rutas reales y con los nombres exactos de su biblioteca y proyecto desechables. Use barras `/` en las rutas. El script ejecuta una solicitud por invocación.

   ```lua
   MCPX_DIRECTORY="C:/ruta/sesion"; MCPX_TEST_LIBRARY="MCPX Scratch"; MCPX_TEST_PROJECT="MCPX-TEST-A"; dofile("D:/ruta/mcpx-free/bridge.lua")
   ```

3. Consulte `resolve_result` con el ID. Cuando responda `read_from_resolve`, conserve `project_id` y `active_timeline`.
4. Pida al agente que consulte `list_media`, prepare la secuencia con `preview_cuts` y después use `request_assembly` con el proyecto y la timeline leídos. Si la consulta devuelve una timeline activa vacía, use `"-"`. Para la prueba de montaje, envíe estos cortes.

   ```json
   [{"media":"B","in":60,"out":180},{"media":"A","in":30,"out":120},{"media":"C","in":0,"out":150}]
   ```

5. Vuelva a ejecutar la misma línea en la consola. `resolve_result` debe devolver `verified_import`, tres clips de video y 360 fotogramas. El receptor lee la timeline resultante y comprueba rutas de medios, fotograma inicial de origen, posición, duración, FPS y elementos de video y audio. Guarde y reabra el proyecto para verificar persistencia.
6. Para probar un marcador, vuelva a consultar el proyecto. Use `request_test_marker` con los IDs actuales y el fotograma relativo 120. Ejecute el receptor y compruebe la respuesta `verified_in_timeline` y el marcador azul de un fotograma. La ejecución solo modifica el proyecto y la biblioteca armados en la consola.

Para la ruta manual, use `export_fcpxml`, abra **File → Import → Timeline** y seleccione el archivo generado. En una biblioteca de prueba, compruebe el orden B–A–C, los cortes en 120 y 210 y la duración de 360 fotogramas. El estado `exported` significa que el archivo se generó y se pudo leer como XML.

## Repetición y recuperación

La inspección admite respuestas de hasta 256 KiB. Una respuesta mayor devuelve
un error explícito. La paginación de timelines extensas queda pendiente.

- El buzón mantiene una solicitud a la vez y el resultado más reciente. Lea la respuesta antes de publicar otra. Si vence el plazo de dos minutos, revise el estado de Resolve antes de solicitar otra edición.
- Mientras la solicitud sigue vigente, repetir el despacho de un montaje busca la timeline por su nombre ligado al ID y verifica sus clips. Una nueva solicitud recibe un ID distinto y crea otra timeline. Un marcador existente de otro ID bloquea la escritura.
- Si falla una comprobación tras importar, busque la timeline `MCPX-<request_id>` y los medios importados. El borrador puede quedar en la biblioteca, donde puede abrirlo e inspeccionarlo.
- La ACL se verifica al crear la sesión. El buzón es local y confía en procesos bajo la misma cuenta de Windows. Mantenga el script, los medios y los directorios de la sesión en ubicaciones que controle el operador. El servidor registra herramienta, estado e ID en stderr.

Para comprobar sin registrar un cliente, ejecute `python smoke.py --session $session request_inspection` y, después del despacho, `python smoke.py --session $session resolve_result '{"request_id":"ID"}'`. La consulta, los marcadores y el montaje se probaron contra Resolve con ese cliente de prueba. Consulte la [auditoría](AUDITORIA.md) y el [plan](PLAN.md) para el alcance medido.


## Licencia y créditos

El código propio de MCPX-Free se distribuye bajo la [licencia MIT](LICENSE).
Se conserva la licencia MIT original de Creative Editor en
[vendor/creative_editor/LICENSE](vendor/creative_editor/LICENSE).

| Proyecto | Aportación a MCPX-Free |
|---|---|
| [Resolve Creative Editor](https://github.com/Anujpal-15th/resolve-creative-editor-mcp) | Función de análisis de timeline y adaptación del patrón de propiedad de sesión del receptor continuo. Commit fijado en THIRD_PARTY_NOTICES.md. |
| [Resolve AI Bridge](https://github.com/flamexnreal/davinci-resolve-ai-bridge-mcp) | Referencia para investigar acceso a archivos nativos de Fusion y correlación de solicitudes. |
| [Resolve Pilot](https://github.com/emircbngl/davinci-resolve-mcp-free) | Referencia para evaluar el intercambio por archivos. El exportador FCPXML actual es propio. |

Los archivos incorporados, sus cambios y la procedencia se detallan en
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). El proyecto es independiente.
Los resultados de los proyectos citados se identifican como evidencia de sus
mantenedores en la [auditoría](AUDITORIA.md).

Las pruebas Python se ejecutan con `python -m unittest -v`. La simulación
`python simulate.py` requiere Windows y la biblioteca Lua instalada con Resolve
en la ruta indicada en ese script. Esa simulación usa objetos de prueba y debe
acompañarse de las comprobaciones en Resolve descritas arriba.
