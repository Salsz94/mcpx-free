# Creative Editor

Source https://github.com/Anujpal-15th/resolve-creative-editor-mcp

Pinned commit `1a5879173c59b736ddd9279b65e77e28037fa671`.

Copyright (c) 2026 Anujpal-15th. MIT license.

- `vendor/creative_editor/analysis.py` contains the extracted `analyze` function from `editor_tools.py`, with a provenance header. It is used for timeline gap and overlap analysis.
- `worker.lua` adapts the session ownership and polling approach from the final dispatcher loop of `resolve_bridge.lua`. It uses MCPX's fixed data receiver and native Fusion file access.

The complete upstream license is retained in `vendor/creative_editor/LICENSE`.

## Architectural references

The following projects informed the design and investigation. The current source
includes no copied files from these projects.

- [Resolve AI Bridge](https://github.com/flamexnreal/davinci-resolve-ai-bridge-mcp) informed investigation of native Fusion file access and request/response correlation. MCPX uses a private local mailbox and fixed operations. Message signing remains outside the current implementation.
- [Resolve Pilot](https://github.com/emircbngl/davinci-resolve-mcp-free/tree/2c9016faf22110517482f7a9efc71ef4e8439b8d) informed evaluation of file interchange. MCPX's FCPXML exporter in `edit.py` is an independent implementation. SRT export remains pending.

Additional repositories reviewed during research are linked in `AUDITORIA.md`.
