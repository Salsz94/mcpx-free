"""Small MCP stdio server for MCPX-Free."""

import argparse
import json
import logging
from pathlib import Path
import sys

from edit import Editor
from live import Mailbox


LOG = logging.getLogger("mcpx")
VERSION = Path(__file__).with_name("VERSION").read_text(encoding="ascii").strip()
VERSIONS = {"2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"}
ID = {"type": "string", "pattern": "^[A-Za-z0-9_-]{1,100}$"}
FRAME = {"type": "integer", "minimum": 0, "maximum": 10_000_000}


def schema(**properties):
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


CUTS = {"type": "array", "minItems": 1, "maxItems": 200,
        "items": schema(**{"media": {"type": "string"}, "in": FRAME, "out": FRAME})}


class Server:
    def __init__(self, editor=None, mailbox=None):
        self.editor = editor
        self.mailbox = mailbox
        self.tools = {}
        self.add("capabilities", "Describe configured workflows and their verification status.",
                 schema(), self.capabilities, True)
        if editor:
            self.add("list_media", "List media IDs and frame counts in the approved manifest.",
                     schema(), editor.catalog, True)
            self.add("preview_cuts", "Validate source ranges and calculate contiguous offsets.",
                     schema(cuts=CUTS), lambda cuts: editor.plan(cuts), True)
            self.add("export_fcpxml", "Write a new FCPXML for operator import into Resolve.",
                     schema(cuts=CUTS), lambda cuts: editor.export(cuts), False)
        if mailbox:
            from cleanup import Cleanup
            cleanup = Cleanup(mailbox)
            self.add("start_takes_analysis", "Analyze archived audio pages locally in the background. Originals remain source references.",
                     schema(snapshot_ids={"type": "array", "items": {"type": "string"}},
                            language={"type": "string"}, remove_duplicates={"type": "boolean"},
                            silence_ms=FRAME),
                     lambda snapshot_ids, language, remove_duplicates, silence_ms: cleanup.start(
                         snapshot_ids, language, remove_duplicates, silence_ms), False)
            self.add("review_takes_analysis", "Read analysis progress and paginated takes, choices and timing summary.",
                     schema(job_id=ID, offset=FRAME, limit=FRAME), cleanup.review, True)
            self.add("choose_take", "Choose a take within a reviewed group. selected_index -1 preserves all alternatives.",
                     schema(job_id=ID, group_id=FRAME, selected_index={"type": "integer"}),
                     cleanup.choose, False)
            self.add("request_apply_takes", "Build up to 25 editable source-linked audio segments on a muted new track. Repeat the same job until verified.",
                     schema(job_id=ID), lambda job_id: cleanup.stage(job_id, False), False)
            activation_inputs = schema(job_id=ID, mute_tracks={
                "type": "array", "items": FRAME})
            activation_inputs["required"] = ["job_id"]
            self.add("request_activate_takes", "Verify cleanup, enable it and disable its source plus optional mute_tracks. Requires permission on real projects.",
                     activation_inputs,
                     lambda job_id, mute_tracks=None: cleanup.stage(job_id, True, mute_tracks), False)
            self.add("request_audio_page", "Read 40 source-linked audio items and archive the page for takes analysis.",
                     schema(project_id=ID, timeline_id=ID, track=FRAME, offset=FRAME),
                     lambda project_id, timeline_id, track, offset: mailbox.stage(
                         "audioscan", project_id, timeline_id, track,
                         lambda request_id: str(offset) + "\n"), False)
            self.add("request_markers", "Read timeline markers for independent beat alignment verification.",
                     schema(), lambda: mailbox.stage("markers"), False)
            self.add("request_timeline", "Queue a track-by-track timeline inspection and gap analysis.",
                     schema(), lambda: mailbox.stage("snapshot"), False)
            self.add("request_inspection", "Queue a Resolve read for operator dispatch.",
                     schema(), lambda: mailbox.stage("inspect"), False)
            self.add("request_test_marker", "Queue a one-frame marker in an armed disposable project.",
                     schema(project_id=ID, timeline_id=ID, frame=FRAME),
                     lambda project_id, timeline_id, frame: mailbox.stage(
                         "marker", project_id, timeline_id, frame), False)
            self.add("request_beat_markers", "Place and verify beat markers from an audio analysis in the armed test timeline.",
                     schema(project_id=ID, timeline_id=ID, frames={
                         "type": "array", "minItems": 1, "maxItems": 200,
                         "items": FRAME}),
                     lambda project_id, timeline_id, frames: mailbox.stage_beats(project_id, timeline_id, frames), False)
            self.add("resolve_result", "Read the latest response for a request ID.",
                     schema(request_id={"type": "string", "pattern": "^[0-9a-f]{32}$"}),
                     lambda request_id: mailbox.result(request_id), True)
            if editor:
                self.add("request_assembly",
                         "Queue an FCPXML import as a new timeline in an armed disposable project. Use '-' when no timeline is active.",
                         schema(project_id=ID, timeline_id=ID, cuts=CUTS),
                         lambda project_id, timeline_id, cuts: mailbox.stage_import(
                             editor, project_id, timeline_id, cuts), False)

    def add(self, name, description, inputs, handler, read_only):
        self.tools[name] = ({"name": name, "description": description, "inputSchema": inputs,
                             "annotations": {"readOnlyHint": read_only, "destructiveHint": False,
                                             "openWorldHint": False}}, handler)

    def capabilities(self):
        return {"fcpxml": "configured_for_manual_import" if self.editor else "unconfigured",
                "resolve": "operator_dispatch" if self.mailbox else "unconfigured",
                "native_mcp_in_free": "studio_only",
                "assembly": "operator_dispatch" if self.editor and self.mailbox else "unconfigured",
                "takes_analysis": "experimental_local_whisper_model_required" if self.mailbox else "unconfigured",
                "takes_editing": "test_project_or_scoped_authorization" if self.mailbox else "unconfigured",
                "visual_selection": "agent_assisted_local_preparation",
                "effects_color_render": "guarded_audit_probes_only"}

    def call(self, params):
        if not isinstance(params, dict) or not isinstance(params.get("name"), str):
            raise ValueError("tools/call requiere el nombre de la herramienta.")
        name = params["name"]
        if name not in self.tools:
            raise ValueError("Herramienta desconocida.")
        definition, handler = self.tools[name]
        arguments = params.get("arguments", {})
        inputs = definition["inputSchema"]
        if (not isinstance(arguments, dict) or not set(inputs["required"]).issubset(arguments)
                or not set(arguments).issubset(inputs["properties"])):
            raise ValueError("Argumentos requeridos o adicionales inválidos.")
        try:
            data = handler(**arguments)
            failed = data.get("status") == "resolve_error"
            LOG.info("%s %s %s", name, data.get("status", "ok"),
                     data.get("request_id", arguments.get("request_id", "")))
        except (ValueError, OSError, KeyError) as exc:
            data, failed = {"status": "error", "message": str(exc)}, True
            LOG.warning("%s %s", name, type(exc).__name__)
        return {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}],
                "isError": failed}

    def serve(self, source, target):
        ready = False
        negotiated = False
        for line in source:
            response = {"jsonrpc": "2.0", "id": None}
            try:
                message = json.loads(line)
            except (ValueError, UnicodeError):
                response["error"] = {"code": -32700, "message": "Parse error"}
            else:
                if (not isinstance(message, dict) or message.get("jsonrpc") != "2.0"
                        or not isinstance(message.get("method"), str)):
                    response["error"] = {"code": -32600, "message": "Invalid request"}
                else:
                    method = message["method"]
                    if "id" not in message:
                        if method == "notifications/initialized" and negotiated:
                            ready = True
                        continue
                    response["id"] = message["id"]
                    params = message.get("params", {})
                    try:
                        if method == "initialize" and not negotiated:
                            version = params.get("protocolVersion") if isinstance(params, dict) else None
                            if not isinstance(version, str):
                                raise ValueError("protocolVersion is required.")
                            negotiated = True
                            result = {"protocolVersion": version if version in VERSIONS else "2025-11-25",
                                      "capabilities": {"tools": {}},
                                      "serverInfo": {"name": "mcpx-free", "version": VERSION}}
                        elif method == "ping":
                            result = {}
                        elif not ready:
                            raise ValueError("MCP session is not initialized.")
                        elif method == "tools/list":
                            result = {"tools": [entry[0] for entry in self.tools.values()]}
                        elif method == "tools/call":
                            result = self.call(params)
                        else:
                            response["error"] = {"code": -32601, "message": "Method not found"}
                    except ValueError as exc:
                        response["error"] = {"code": -32602, "message": str(exc)}
                    if "error" not in response:
                        response["result"] = result
            target.write((json.dumps(response, ensure_ascii=False) + "\n").encode("utf-8"))
            target.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version="MCPX-Free " + VERSION)
    parser.add_argument("--media-root", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--session", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    editor = None
    options = (args.media_root, args.output, args.manifest)
    if any(options):
        if not all(options):
            parser.error("--media-root, --manifest and --output must be supplied together")
        editor = Editor(args.media_root, args.output, json.loads(args.manifest.read_text(encoding="utf-8-sig")))
    mailbox = Mailbox(args.session) if args.session else None
    Server(editor, mailbox).serve(sys.stdin.buffer, sys.stdout.buffer)


if __name__ == "__main__":
    main()
