from fractions import Fraction
import json
import runpy
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
import xml.etree.ElementTree as ET

from edit import Editor
from live import Mailbox
from smoke import Client


CUTS = [{"media": "B", "in": 60, "out": 180},
        {"media": "A", "in": 30, "out": 120},
        {"media": "C", "in": 0, "out": 150}]


class Fixture(TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.output = self.root / "output"
        self.output.mkdir()
        self.manifest = {"fps": 30, "width": 1920, "height": 1080, "media": {}}
        for key in "ABC":
            name = f"{key} sample.mov"
            (self.root / name).touch()
            self.manifest["media"][key] = {"file": name, "frames": 180, "audio_channels": 1}
        self.editor = Editor(self.root, self.output, self.manifest)

    def test_export_has_exact_timing_audio_and_file_uri(self):
        result = self.editor.export(CUTS)
        tree = ET.parse(result["path"])
        clips = tree.findall(".//asset-clip")
        self.assertEqual(len(clips), 3)
        for attribute, expected in (("offset", [0, 120, 210]), ("start", [60, 30, 0]),
                                    ("duration", [120, 90, 150])):
            self.assertEqual([Fraction(c.attrib[attribute][:-1]) * 30 for c in clips], expected)
        assets = tree.findall(".//asset")
        self.assertEqual([asset.attrib["name"] for asset in assets],
                         ["B sample.mov", "A sample.mov", "C sample.mov"])
        self.assertTrue(all(asset.attrib["audioChannels"] == "1" for asset in assets))
        self.assertTrue(all("%20" in node.attrib["src"] for node in tree.findall(".//media-rep")))

    def test_rejects_out_of_range_boolean_and_traversal(self):
        for invalid in ([], [{"media": "X", "in": 0, "out": 1}],
                        [{"media": "A", "in": True, "out": 1}],
                        [{"media": "A", "in": 0, "out": 181}]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.editor.export(invalid)
        self.manifest["media"]["B"]["file"] = "../sample.mov"
        with self.assertRaises(ValueError):
            self.editor.export(CUTS)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_stdio_schema_validation_and_export(self):
        manifest = self.root / "manifest.json"
        manifest.write_text(json.dumps(self.manifest), encoding="utf-8")
        with Client(["--media-root", str(self.root), "--output", str(self.output),
                     "--manifest", str(manifest)]) as client:
            definitions = {tool["name"]: tool for tool in client.request("tools/list")["tools"]}
            self.assertEqual(set(definitions), {"capabilities", "list_media", "preview_cuts", "export_fcpxml"})
            self.assertFalse(definitions["preview_cuts"]["inputSchema"]["additionalProperties"])
            self.assertEqual([item["id"] for item in client.call("list_media")["media"]], list("ABC"))
            self.assertEqual(client.call("preview_cuts", cuts=CUTS)["duration_frames"], 360)
            self.assertEqual(client.call("export_fcpxml", cuts=CUTS)["status"], "exported")
            self.assertEqual(client.call("export_fcpxml", cuts=[{}])["status"], "error")

    def test_stdio_mailbox_pending_correlation_expiry_and_simulated_reply(self):
        for name in ("request.txt", "response.txt", "lock"):
            (self.root / name).write_bytes(b"\0" if name == "lock" else b"")
        options = ["--session", str(self.root)]
        with Client(options) as client:
            staged = client.call("request_inspection")
            request_id = staged["request_id"]
            self.assertEqual(client.call("resolve_result", request_id=request_id)["status"],
                             "pending_operator")
            self.assertEqual(client.call("request_inspection")["status"], "error")
            self.assertEqual(client.call("request_test_marker", project_id="../", timeline_id="y",
                                         frame=1)["status"], "error")
            data = ["DaVinci Resolve", "21.1.0.17", "Prueba ñ", "project", ""]
            response = "|".join([request_id, "ok", *(s.encode().hex() for s in data), "END"])
            (self.root / "response.txt").write_bytes(response.encode() + b"\n")
            result = client.call("resolve_result", request_id=request_id)
            self.assertEqual(result["project"], "Prueba ñ")
            self.assertEqual(result["edition"], "free")
            new_id = client.call("request_inspection")["request_id"]
            (self.root / "request.txt").write_text(f"{new_id} 1 inspect - - 0", encoding="ascii")
            self.assertEqual(client.call("resolve_result", request_id=new_id)["status"], "error")

    def test_assembly_staging_creates_bound_xml_and_expectations(self):
        for name in ("request.txt", "response.txt", "lock"):
            (self.root / name).write_bytes(b"\0" if name == "lock" else b"")
        mailbox = Mailbox(self.root)
        with self.assertRaises(ValueError):
            mailbox.stage_import(self.editor, "project", "-", [{"media": "B", "in": 0, "out": 181}])
        self.assertFalse(list(self.root.glob("*.fcpxml")))
        staged = mailbox.stage_import(self.editor, "project", "-", CUTS)
        request = (self.root / "request.txt").read_text(encoding="ascii").splitlines()
        token = staged["request_id"]
        self.assertEqual(request[0].split()[2:], ["assemble", "project", "-", "30"])
        self.assertEqual([line.split()[1:] for line in request[1:]],
                         [line.split() for line in ("0 120 60 1", "120 90 30 1", "210 150 0 1")])
        self.assertEqual(ET.parse(self.root / f"MCPX-{token}.fcpxml").find(".//project").attrib["name"],
                         f"MCPX-{token}")

    def test_damaged_mailbox_returns_error_and_server_survives(self):
        for name in ("request.txt", "response.txt", "lock"):
            (self.root / name).write_bytes(b"0")
        with Client(["--session", str(self.root)]) as client:
            self.assertEqual(client.call("request_inspection")["status"], "error")
            self.assertEqual(client.call("resolve_result", request_id="a" * 32)["status"], "error")
            self.assertIn("resolve", client.call("capabilities"))

    def test_panel_does_not_report_stale_or_stopped_worker_as_active(self):
        panel = runpy.run_path(str(Path(__file__).with_name("launcher.pyw")))
        heartbeat = self.root / "heartbeat.txt"
        self.assertFalse(panel["heartbeat_state"](self.root))
        heartbeat.write_text(str(int(time.time())), encoding="ascii")
        self.assertTrue(panel["heartbeat_state"](self.root))
        heartbeat.write_text(str(int(time.time()) - 10), encoding="ascii")
        self.assertFalse(panel["heartbeat_state"](self.root))
        heartbeat.write_text("stopped", encoding="ascii")
        self.assertFalse(panel["heartbeat_state"](self.root))

    def test_oversized_response_is_reported_without_blocking_other_requests(self):
        for name in ("request.txt", "response.txt", "lock"):
            (self.root / name).write_bytes(b"0" if name == "lock" else b"")
        with Client(["--session", str(self.root)]) as client:
            request_id = client.call("request_inspection")["request_id"]
            response = request_id + "|error|" + "61" * 131_100 + "|END\n"
            (self.root / "response.txt").write_bytes(response.encode("ascii"))
            result = client.call("resolve_result", request_id=request_id)
            self.assertEqual(result["status"], "error")
            self.assertIn("256 KiB", result["message"])
            self.assertEqual(client.call("resolve_result", request_id="b" * 32)["status"], "error")
            self.assertIn("resolve", client.call("capabilities"))
            (self.root / "response.txt").write_text(request_id + "|error|61|END\n", encoding="ascii")
            self.assertEqual(client.call("resolve_result", request_id=request_id)["status"], "resolve_error")
