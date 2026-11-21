"""Run real Resolve checks through MCP and fixed, test-only Lua probes.

Requires the operator to open and arm a disposable MCPX-TEST project.
Media and detailed results stay in the private session directory.
"""

import argparse
from copy import deepcopy
import hashlib
import json
import shutil
from pathlib import Path
import time
import traceback
import uuid

from cleanup import build_plan, frame_rate
from live import Mailbox
from selection import prepare_selection
from smoke import Client


class Audit:
    def __init__(self, session, fixture, beat_analysis):
        self.session = session.resolve(strict=True)
        self.fixture = fixture.resolve(strict=True)
        self.beats = json.loads(beat_analysis.read_text(encoding="utf-8"))
        self.run_id = uuid.uuid4().hex
        self.directory = self.session / ("audit-" + self.run_id)
        self.directory.mkdir()
        self.results = []
        self.baseline = None
        self.project_id = None

    def finish(self, client, request):
        if "request_id" not in request:
            raise RuntimeError(request)
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            result = client.call("resolve_result", request_id=request["request_id"])
            if result.get("status") == "pending_operator":
                time.sleep(.3)
                continue
            if result.get("status") in ("error", "resolve_error"):
                raise RuntimeError(result)
            return result
        raise TimeoutError(request)

    def call(self, name, **arguments):
        return self.finish(self.client, self.client.call(name, **arguments))

    def state(self):
        state = self.call("request_inspection")
        if not state["project"].startswith("MCPX-TEST-"):
            raise RuntimeError("Open and arm the disposable test project")
        if self.project_id and state["project_id"] != self.project_id:
            raise RuntimeError("Project changed during the audit")
        self.project_id = state["project_id"]
        return state

    def probe(self, action, extra=None):
        state = self.state()
        body = action + " " + self.run_id + "\n" + (extra + "\n" if extra else "")
        request = Mailbox(self.session).stage("audit", state["project_id"],
                                             state["active_timeline"],
                                             prepare=lambda request_id: body)
        result = self.finish(self.client, request)
        if result.get("status") != "probe_result":
            raise RuntimeError(result)
        return result["evidence"]

    def assemble(self, fixture, cuts=None):
        manifest = json.loads((fixture / "manifest.json").read_text(encoding="utf-8"))
        if cuts is None:
            cuts = [{"media": key, "in": 0, "out": item["frames"]}
                    for key, item in manifest["media"].items()]
        state = self.state()
        options = ["--session", str(self.session), "--media-root", str(fixture / "media"),
                   "--manifest", str(fixture / "manifest.json"), "--output", str(fixture / "output")]
        with Client(options, stderr=self.logs) as client:
            preview = client.call("preview_cuts", cuts=cuts)
            if preview.get("status") == "error":
                raise RuntimeError(preview)
            result = self.finish(client, client.call("request_assembly",
                project_id=state["project_id"], timeline_id=state["active_timeline"], cuts=cuts))
        snapshot = self.call("request_timeline")
        assert result["timeline_id"] == snapshot["timeline_id"]
        assert snapshot["end_frame"] - snapshot["start_frame"] == preview["duration_frames"]
        return {"assembly": result, "snapshot": snapshot, "cuts": cuts}

    def record(self, name, function, access="Flujo MCP"):
        started = time.monotonic()
        try:
            evidence = function()
            result = {"name": name, "status": "PASS", "access": access, "evidence": evidence}
        except Exception as error:
            result = {"name": name, "status": "FAIL", "access": access,
                      "error": str(error), "traceback": traceback.format_exc()}
        result["seconds"] = round(time.monotonic() - started, 2)
        self.results.append(result)
        latest = {entry["name"]: entry for entry in self.results}
        (self.directory / "report.json").write_text(json.dumps({
            "run_id": self.run_id, "project_id": self.project_id, "results": self.results,
            "latest_results": [latest[name] for name in sorted(latest)],
            "source_sha256_at_report": {name: hashlib.sha256(
                Path(__file__).with_name(name).read_bytes()).hexdigest()
                for name in ("audit.py", "audit_probe.lua", "audio_edit.lua", "cleanup.py", "bridge.lua", "server.py", "live.py")}},
            ensure_ascii=False, indent=2), encoding="utf-8")
        print(result["status"], name, result.get("error", ""), flush=True)
        return result

    def selected(self):
        result = self.assemble(self.fixture)
        self.baseline = result
        assert len(result["snapshot"]["clips"]) == 16
        return {"timeline": result["assembly"]["timeline"], "clips": 8, "seconds": 12}

    def every_beat(self):
        original = json.loads((self.fixture / "selection.json").read_text(encoding="utf-8"))
        frames = sorted({event["frame"] for event in self.beats["events"] if 0 < event["frame"] < 360})
        boundaries = [0, *frames, 360]
        plan = deepcopy(original)
        plan["shots"] = []
        for index, (first, last) in enumerate(zip(boundaries, boundaries[1:])):
            shot = deepcopy(original["shots"][index % len(original["shots"])])
            shot["frames"] = last - first
            plan["shots"].append(shot)
        folder = self.directory / "every-beat"
        prepare_selection(plan, folder)
        assembled = self.assemble(folder)
        self.call("request_beat_markers", project_id=self.project_id,
                  timeline_id=assembled["assembly"]["timeline_id"], frames=frames)
        markers = self.call("request_markers")
        snapshot = assembled["snapshot"]
        start = snapshot["start_frame"]
        actual = sorted(item["start"] - start for item in snapshot["clips"]
                        if item["track_type"] == "video" and item["start"] != start)
        assert actual == frames == sorted(marker["frame"] for marker in markers["markers"])
        assert len([item for item in snapshot["clips"] if item["track_type"] == "video"]) == len(frames) + 1
        return {"timeline": assembled["assembly"]["timeline"], "beats": len(frames),
                "shots": len(frames) + 1, "cut_frames": actual}

    def uniform(self):
        original = json.loads((self.fixture / "selection.json").read_text(encoding="utf-8"))
        plan = deepcopy(original)
        plan["shots"] = []
        for index in range(12):
            shot = deepcopy(original["shots"][index % len(original["shots"])])
            shot["frames"] = 30
            plan["shots"].append(shot)
        folder = self.directory / "uniform"
        prepare_selection(plan, folder)
        result = self.assemble(folder)
        items = [item for item in result["snapshot"]["clips"] if item["track_type"] == "video"]
        assert len(items) == 12 and all(item["end"] - item["start"] == 30 for item in items)
        return {"timeline": result["assembly"]["timeline"], "shots": 12, "frames_each": 30}

    def order_and_ranges(self):
        manifest = json.loads((self.fixture / "manifest.json").read_text())
        keys = list(reversed(manifest["media"]))[:3]
        cuts = [{"media": key, "in": 2, "out": min(20, manifest["media"][key]["frames"])} for key in keys]
        result = self.assemble(self.fixture, cuts)
        items = sorted((item for item in result["snapshot"]["clips"] if item["track_type"] == "video"),
                       key=lambda item: item["start"])
        assert [Path(item["path"]).name for item in items] == [manifest["media"][key]["file"] for key in keys]
        assert all(item["source_start"] == 2 for item in items)
        return {"order": keys, "source_in": 2, "timeline": result["assembly"]["timeline"]}

    def render(self):
        import av
        started = self.probe("renderstart")
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            status = self.probe("renderstatus", started["job"])
            if status["status"] in ("Complete", "Stopped"):
                break
            if status["status"] in ("Failed", "Cancelled"):
                raise RuntimeError(status)
            time.sleep(1)
        else:
            raise TimeoutError("Resolve render timeout")
        files = list(self.directory.glob(started["filename"] + ".*"))
        path = next(path for path in files if path.suffix.lower() in (".mp4", ".mov"))
        with av.open(str(path)) as media:
            frames = list(media.decode(video=0))
            assert len(frames) == 15
            average = frames[7].to_ndarray(format="rgb24").mean(axis=(0, 1)).tolist()
        with av.open(str(path)) as media:
            samples = sum(frame.samples for frame in media.decode(audio=0))
            assert samples > 0
        return {"file": str(path), "frames": len(frames), "audio_samples": samples,
                "mean_rgb": average, "timeline": started["timeline"],
                "job": started["job"], "render_status": status}

    def color(self):
        before = self.render()
        evidence = self.probe("color")
        after = self.render()
        difference = sum(abs(a - b) for a, b in zip(before["mean_rgb"], after["mean_rgb"]))
        assert difference > 1, "LUT metadata changed but rendered pixels did not"
        return {**evidence, "before": before, "after": after, "rgb_difference": difference}

    def audio_pages(self):
        state = self.state()
        offset = 0
        requests = []
        clips = []
        while True:
            request = self.client.call("request_audio_page", project_id=self.project_id,
                                       timeline_id=state["active_timeline"], track=1, offset=offset)
            page = self.finish(self.client, request)
            requests.append(request["request_id"])
            clips.extend(page["clips"])
            offset += len(page["clips"])
            if offset == page["total"]:
                break
            if not page["clips"]:
                raise RuntimeError("Empty audio page")
        page["clips"], page["offset"] = clips, 0
        return requests, page

    def local_voice(self):
        self.probe("audiofixture")
        pages, self.audio_source = self.audio_pages()
        request = self.client.call("start_takes_analysis", snapshot_ids=pages, language="es",
                                   remove_duplicates=True, silence_ms=700)
        assert request["status"] == "analyzing", request
        self.voice_job = request["job_id"]
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            result = self.client.call("review_takes_analysis", job_id=self.voice_job, offset=0, limit=40)
            if result["status"] == "ready":
                self.voice_review = result
                # The controlled fixture repeats the same phrase twice with a
                # known silent gap. A transcript alone is insufficient proof.
                assert result["summary"]["segments"] == 1, result
                assert result["summary"]["discarded_takes"] == 1, result
                assert 5 < result["summary"]["output_seconds"] < 7, result
                assert len(result["groups"]) == 1 and len(result["groups"][0]["takes"]) == 2, result
                return result["summary"]
            if result["status"] in ("error", "interrupted"):
                raise RuntimeError(result)
            time.sleep(1)
        raise TimeoutError("Local voice analysis timeout")

    def apply_voice(self):
        assert getattr(self, "voice_job", None), "Voice analysis unavailable"
        for _ in range(100):
            result = self.call("request_apply_takes", job_id=self.voice_job)
            if result["status"] == "cleanup_verified":
                break
            assert result["status"] == "cleanup_building", result
        else:
            raise RuntimeError("Cleanup did not finish")
        self.voice_track = result["track"]
        snapshot = self.call("request_timeline")
        original = [item for item in snapshot["clips"] if item["track_type"] == "audio" and item["track"] == 1]
        edited = [item for item in snapshot["clips"] if item["track_type"] == "audio" and item["track"] == self.voice_track]
        assert len(original) == 1 and original[0]["id"] == self.audio_source["clips"][0]["id"]
        assert len(edited) == result["total_segments"]
        flags = self.probe("trackstate")
        assert flags["A" + str(self.voice_track)] == "false"
        return result

    def activate_voice(self):
        result = self.call("request_activate_takes", job_id=self.voice_job, mute_tracks=[1])
        assert result["status"] == "cleanup_active"
        flags = self.probe("trackstate")
        assert flags["A1"] == "false" and flags["A" + str(self.voice_track)] == "true"
        return result

    def choose_voice(self):
        assert self.voice_review["groups"][0]["selected_index"] == 1
        first = self.client.call("choose_take", job_id=self.voice_job, group_id=1, selected_index=0)
        both = self.client.call("choose_take", job_id=self.voice_job, group_id=1, selected_index=-1)
        last = self.client.call("choose_take", job_id=self.voice_job, group_id=1, selected_index=1)
        assert first["summary"]["segments"] == last["summary"]["segments"] == 1
        assert both["summary"]["segments"] == 2
        assert both["summary"]["output_seconds"] > 11 > last["summary"]["output_seconds"]
        return {"first": first["summary"], "both": both["summary"], "last": last["summary"]}

    def stale_voice(self):
        from cleanup import write_json
        before = self.probe("trackstate")
        job = json.loads((self.session / "cleanup" / (self.voice_job + ".json")).read_text(encoding="utf-8"))
        job["id"] = uuid.uuid4().hex
        job["snapshot"]["clips"][0]["id"] = str(uuid.uuid4())
        write_json(self.session / "cleanup" / (job["id"] + ".json"), job)
        request = self.client.call("request_apply_takes", job_id=job["id"])
        for _ in range(100):
            result = self.client.call("resolve_result", request_id=request["request_id"])
            if result.get("status") != "pending_operator":
                break
            time.sleep(.2)
        assert result["status"] == "resolve_error" and "Source clip disappeared" in result["message"], result
        after = self.probe("trackstate")
        assert before == after
        return {"stale_clip_rejected": True, "track_count_and_enabled_flags_unchanged": True}

    def stress_audio(self):
        from cleanup import write_json
        snapshot = deepcopy(self.audio_source)
        snapshot["clips"] = snapshot["clips"][:1]
        job_id = getattr(self, "stress_resume_job", None) or uuid.uuid4().hex
        segments = []
        record = 0
        for index in range(400):
            length = index % 5 + 1
            first = index % 100
            segments.append({"source": 0, "in": first, "out": first + length,
                             "frames": length, "record": record})
            record += length
        job = {"id": job_id, "status": "ready", "snapshot": snapshot,
               "plan": {"segments": segments, "duration_frames": record},
               "summary": {}, "groups": []}
        write_json(self.session / "cleanup" / (job_id + ".json"), job)
        for _ in range(30):
            result = self.call("request_apply_takes", job_id=job_id)
            print("AUDIO_STRESS", result.get("completed_segments"), "/ 400", flush=True)
            if result["status"] == "cleanup_verified":
                break
            assert result["status"] == "cleanup_building", result
        else:
            raise RuntimeError("400-clip operation did not finish")
        before = self.probe("trackstate")
        repeated = self.call("request_apply_takes", job_id=job_id)
        after = self.probe("trackstate")
        assert repeated["completed_segments"] == 400 and before["tracks"] == after["tracks"]
        state = self.state()
        clips = []
        while len(clips) < 400:
            page = self.call("request_audio_page", project_id=self.project_id,
                             timeline_id=state["active_timeline"], track=result["track"], offset=len(clips))
            assert page["clips"]
            clips.extend(page["clips"])
        for clip, expected in zip(clips, segments):
            assert clip["start"] - snapshot["start_frame"] == expected["record"]
            assert clip["end"] - clip["start"] == expected["frames"]
            assert abs(clip["source_time"] * 30 - expected["in"]) < .001
        return {"segments": len(clips), "track": result["track"], "duration_frames": record,
                "pages": 10, "replay_duplicate_tracks": False, "timing_errors": 0}

    def guard(self):
        state = self.state()
        request = self.client.call("request_audio_page", project_id=self.project_id,
                                   timeline_id="wrong-timeline", track=1, offset=0)
        for _ in range(100):
            result = self.client.call("resolve_result", request_id=request["request_id"])
            if result.get("status") != "pending_operator":
                break
            time.sleep(.2)
        assert result["status"] == "resolve_error" and "changed" in result["message"]
        assert self.state()["active_timeline"] == state["active_timeline"]
        return {"stale_timeline_rejected": True}

    def run(self):
        with (self.directory / "server.log").open("a", encoding="utf-8") as self.logs, Client(
                ["--session", str(self.session)], stderr=self.logs) as self.client:
            state = self.state()
            self.record("01 Conexión y entorno real", lambda: {
                "edition": state["edition"], "version": state["version"], "project": state["project"]})
            self.record("02 Montaje con selección visual previa del agente", self.selected, "Agente local + MCP")
            self.record("03 Una toma nueva en cada beat detectado", self.every_beat, "BeatDetector local + MCP")
            self.record("04 Todos los clips con la misma duración", self.uniform, "Agente local + MCP")
            self.record("05 Reordenar tomas y cambiar sus rangos de origen", self.order_and_ranges)
            for action, title in (("transform", "06 Zoom, posición y rotación"),
                                  ("speed", "07 Cambiar velocidad"),
                                  ("volume", "08 Volumen y paneo"),
                                  ("fades", "09 Fundidos de audio"),
                                  ("fusion", "10 Efecto Glow en Fusion"),
                                  ("color", "11 Color mediante LUT"),
                                  ("title", "12 Título editable Text+")):
                self.record(title, self.color if action == "color" else lambda action=action: self.probe(action),
                            "Prueba API por puente, herramienta general pendiente")
            self.record("13 Render de video y audio en Resolve Free", self.render, "Prueba API por puente")
            self.record("14 Transcripción local y plan de limpieza de voz", self.local_voice)
            self.record("20 Elegir otra toma o conservar ambas desde Codex", self.choose_voice)
            self.record("15 Cortes de voz editables desde el medio original", self.apply_voice)
            self.record("16 Activar pista verificada y silenciar respaldo", self.activate_voice)
            self.record("21 Rechazar un clip de origen que cambió", self.stale_voice)
            self.record("17 400 segmentos, paginación, precisión y repetición", self.stress_audio)
            self.record("18 Rechazar un cambio de timeline", self.guard)
            self.record("19 Guardar, cerrar y reabrir el proyecto", lambda: self.probe("persist"), "Prueba API por puente")
        print(str(self.directory / "report.json"), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--beats", type=Path, required=True)
    parser.add_argument("--voice", type=Path, required=True, help="Private WAV speech fixture")
    args = parser.parse_args()
    audit = Audit(args.session, args.fixture, args.beats)
    shutil.copyfile(args.voice, audit.directory / "voice.wav")
    lines = ['TITLE "MCPX audit tint"', "LUT_3D_SIZE 2", "DOMAIN_MIN 0 0 0", "DOMAIN_MAX 1 1 1"]
    for blue in (0, 1):
        for green in (0, 1):
            for red in (0, 1):
                lines.append(f"{red * .6:.6f} {green:.6f} {blue * .7:.6f}")
    (audit.directory / "tint.cube").write_text("\n".join(lines) + "\n", encoding="ascii")
    print("AUDIT_DIRECTORY=" + str(audit.directory), flush=True)
    audit.run()


if __name__ == "__main__":
    main()
