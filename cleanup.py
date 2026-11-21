"""Source-linked narration cleanup plans and asynchronous local transcription."""

import argparse
from difflib import SequenceMatcher
from fractions import Fraction
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

from edit import integer, safe_path
from live import REQUEST_ID, replace_file


def write_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    replace_file(temporary, path)


def process_alive(pid):
    if os.name == "nt":
        import ctypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def frame_rate(value):
    rates = {"23.976": Fraction(24000, 1001), "29.97": Fraction(30000, 1001),
             "59.94": Fraction(60000, 1001)}
    rate = rates.get(str(value), Fraction(str(value)))
    if not 1 <= rate <= 120:
        raise ValueError("FPS de timeline no válido.")
    return rate


def normalized(text):
    return " ".join(re.findall(r"\w+", text.casefold()))


def group_takes(takes, remove_duplicates):
    """Only identical adjacent sentences are preselected for removal."""
    groups = []
    for take in takes:
        previous = groups[-1]["takes"][-1] if groups else None
        similar = False
        exact = False
        if previous and take["timeline_time"] - previous["timeline_end"] < 25:
            first, second = normalized(previous["text"]), normalized(take["text"])
            if min(len(first.split()), len(second.split())) >= 4:
                exact = first == second
                similar = exact or SequenceMatcher(None, first, second).ratio() >= .85
        if similar:
            group = groups[-1]
            group["takes"].append(take)
            all_identical = len({normalized(item["text"]) for item in group["takes"]}) == 1
            confident = min(item["confidence"] for item in group["takes"]) >= .8
            group["selected_index"] = len(group["takes"]) - 1 if (
                remove_duplicates and all_identical and confident) else -1
            group["reason"] = "repetición exacta" if all_identical else "variante para revisar"
        else:
            groups.append({"id": len(groups) + 1, "takes": [take],
                           "selected_index": 0, "reason": "voz detectada"})
    return groups


def build_plan(snapshot, groups, pause_ms=120):
    fps = frame_rate(snapshot["fps"])
    segments = []
    record = 0
    pause_frames = round(Fraction(pause_ms, 1000) * fps)
    for group in groups:
        chosen = group["takes"] if group["selected_index"] == -1 else [
            group["takes"][group["selected_index"]]]
        for take in chosen:
            clip = snapshot["clips"][take["source"]]
            # Quantize each source interval once and accumulate integer destination frames.
            lower = math.ceil(Fraction(str(clip["source_time"])) * fps)
            upper = math.floor(Fraction(str(clip["source_time"])) * fps + clip["end"] - clip["start"])
            first = max(lower, math.floor(Fraction(str(take["start"])) * fps))
            last = min(upper, math.ceil(Fraction(str(take["end"])) * fps))
            if last <= first:
                continue
            if segments and segments[-1]["source"] == take["source"] and first < segments[-1]["out"]:
                previous = segments[-1]
                extension = max(0, last - previous["out"])
                previous["out"] += extension
                previous["frames"] += extension
                record = previous["record"] + previous["frames"]
                continue
            if segments:
                record += pause_frames
            segments.append({"source": take["source"], "in": first, "out": last,
                             "frames": last - first, "record": record, "text": take["text"],
                             "group": group["id"]})
            record += last - first
    if not segments:
        raise ValueError("El análisis no encontró intervalos de voz utilizables.")
    if len(segments) > 2000:
        raise ValueError("El plan supera 2000 segmentos. Divida la locución en partes.")
    return {"segments": segments, "duration_frames": record, "fps": str(fps)}


def analyze_snapshot(snapshot, options, progress):
    from faster_whisper import WhisperModel

    model = WhisperModel(options["model"], device="cpu", compute_type="int8",
                         download_root=options["model_cache"], local_files_only=True)
    fps = frame_rate(snapshot["fps"])
    takes = []
    transcripts = {}
    for index, clip in enumerate(snapshot["clips"]):
        if clip["speed"] != 100:
            raise ValueError("La primera versión requiere clips a velocidad 100%.")
        progress(f"Transcribiendo clip {index + 1} de {len(snapshot['clips'])}")
        path = clip["path"]
        if path not in transcripts:
            stream, _ = model.transcribe(path, language=options["language"], vad_filter=True,
                                        vad_parameters={"min_silence_duration_ms": options["silence_ms"],
                                                        "speech_pad_ms": 80},
                                        word_timestamps=True, beam_size=5)
            words = []
            for segment in stream:
                if segment.no_speech_prob > .6:
                    continue
                for word in segment.words or []:
                    words.append({"start": word.start, "end": word.end,
                                  "word": word.word, "probability": word.probability})
            transcripts[path] = words
        start = clip["source_time"]
        end = start + float(Fraction(clip["end"] - clip["start"], 1) / fps)
        active = [word for word in transcripts[path] if word["end"] > start and word["start"] < end]
        chunks = []
        for word in active:
            gap = word["start"] - chunks[-1][-1]["end"] if chunks else 0
            sentence_end = chunks and re.search(r"[.!?]$", chunks[-1][-1]["word"])
            if not chunks or gap >= options["silence_ms"] / 1000 or (sentence_end and gap >= .12):
                chunks.append([])
            chunks[-1].append(word)
        for chunk in chunks:
            first = max(start, chunk[0]["start"] - .08)
            last = min(end, chunk[-1]["end"] + .12)
            takes.append({"source": index, "start": first, "end": last,
                          "text": "".join(word["word"] for word in chunk).strip(),
                          "confidence": sum(word["probability"] for word in chunk) / len(chunk),
                          "timeline_time": (clip["start"] - snapshot["start_frame"]) / float(fps) + first - start,
                          "timeline_end": (clip["start"] - snapshot["start_frame"]) / float(fps) + last - start})
    groups = group_takes(takes, options["remove_duplicates"])
    plan = build_plan(snapshot, groups, options["pause_ms"])
    return groups, plan


class Cleanup:
    def __init__(self, mailbox):
        self.mailbox = mailbox
        self.directory = mailbox.directory / "cleanup"
        self.directory.mkdir(exist_ok=True)

    def path(self, job_id):
        if not isinstance(job_id, str) or not REQUEST_ID.fullmatch(job_id):
            raise ValueError("ID de análisis no válido.")
        return safe_path(self.directory, job_id + ".json")

    def load(self, job_id):
        return json.loads(self.path(job_id).read_text(encoding="utf-8"))

    def start(self, snapshot_ids, language, remove_duplicates, silence_ms):
        if language not in ("es", "en"):
            raise ValueError("Idioma admitido: es o en.")
        if type(remove_duplicates) is not bool:
            raise ValueError("remove_duplicates debe ser booleano.")
        integer(silence_ms, 300, 5000)
        if not isinstance(snapshot_ids, list) or not 1 <= len(snapshot_ids) <= 100:
            raise ValueError("Indique las páginas de audio consultadas.")
        pages = []
        for request_id in snapshot_ids:
            if not isinstance(request_id, str) or not REQUEST_ID.fullmatch(request_id):
                raise ValueError("ID de página no válido.")
            path = safe_path(self.mailbox.directory, "audio-snapshot-" + request_id + ".json")
            pages.append(json.loads(path.read_text(encoding="utf-8")))
        pages.sort(key=lambda page: page["offset"])
        snapshot = {key: value for key, value in pages[0].items() if key != "clips"}
        clips = []
        for page in pages:
            for key in ("project_id", "timeline_id", "fps", "start_frame", "track", "track_type", "total"):
                if page[key] != snapshot[key]:
                    raise ValueError("Las páginas pertenecen a estados distintos.")
            if page["offset"] != len(clips):
                raise ValueError("Faltan páginas o están duplicadas.")
            clips.extend(page["clips"])
        if len(clips) != snapshot["total"] or not clips:
            raise ValueError("Lea todas las páginas de la pista de origen.")
        if snapshot["track_type"] not in ("mono", "stereo"):
            raise ValueError("La primera versión admite pistas mono y estéreo.")
        if any(second["start"] < first["end"] for first, second in zip(clips, clips[1:])):
            raise ValueError("La pista de origen contiene clips solapados.")
        snapshot["clips"] = clips
        job_id = uuid.uuid4().hex
        path = self.directory / (job_id + ".json")
        job = {"id": job_id, "status": "analyzing", "created_at": time.time(),
               "updated_at": time.time(), "progress": "Cargando transcriptor local",
               "snapshot": snapshot, "options": {"language": language,
                   "remove_duplicates": remove_duplicates, "silence_ms": silence_ms,
                   "pause_ms": 120, "model": "base",
                   "model_cache": str(Path(__file__).parent / ".scratch/models")}}
        write_json(path, job)
        log_path = self.directory / (job_id + ".log")
        try:
            with log_path.open("xb") as log:
                subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--job", str(path)],
                                 stdout=log, stderr=subprocess.STDOUT, close_fds=True,
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        except OSError as error:
            job.update(status="error", error=str(error))
            write_json(path, job)
            raise
        return {"status": "analyzing", "job_id": job_id}

    def review(self, job_id, offset, limit):
        integer(offset, 0, 100_000)
        integer(limit, 1, 40)
        job = self.load(job_id)
        if job["status"] == "analyzing":
            abandoned = (not process_alive(job["pid"]) if job.get("pid")
                         else time.time() - job["updated_at"] > 120)
            if abandoned:
                return {"id": job_id, "status": "interrupted",
                        "message": "El proceso local de análisis terminó. Inicie otro análisis con las mismas páginas."}
        result = {key: job[key] for key in ("id", "status", "updated_at", "progress") if key in job}
        if job["status"] == "error":
            result["message"] = job["error"]
        if job["status"] == "ready":
            result.update(summary=job["summary"], groups=job["groups"][offset:offset + limit],
                          offset=offset, total_groups=len(job["groups"]))
        return result

    def choose(self, job_id, group_id, selected_index):
        with self.mailbox.lock():
            job = self.load(job_id)
            if job["status"] != "ready":
                raise ValueError("El análisis todavía no está listo.")
            if job.get("applied"):
                raise ValueError("El plan ya se preparó para Resolve. Cree otro análisis para cambiarlo.")
            integer(group_id, 1, len(job["groups"]))
            group = job["groups"][group_id - 1]
            integer(selected_index, -1, len(group["takes"]) - 1)
            group["selected_index"] = selected_index
            job["plan"] = build_plan(job["snapshot"], job["groups"], job["options"]["pause_ms"])
            summarize(job)
            write_json(self.path(job_id), job)
        return {"status": "ready", "summary": job["summary"]}

    def stage(self, job_id, activate, mute_tracks=None):
        with self.mailbox.lock():
            job = self.load(job_id)
            if job["status"] != "ready":
                raise ValueError("El plan no está listo.")
            state = self.mailbox.directory / ("cleanup-state-" + job_id + ".txt")
            if not state.exists():
                with state.open("x", encoding="ascii") as output:
                    output.write("new\n")
            else:
                safe_path(self.mailbox.directory, state.name)
            job["applied"] = True
            write_json(self.path(job_id), job)
        snapshot, plan = job["snapshot"], job["plan"]
        tracks = sorted(set([snapshot["track"], *(mute_tracks or [])])) if activate else []
        for track in tracks:
            integer(track, 1, 1000)
        mute = ",".join(str(track) for track in tracks) or "-"
        header = f"{job_id} {snapshot['track']} {len(snapshot['clips'])} {len(plan['segments'])} {float(frame_rate(snapshot['fps'])):.12g} {snapshot['track_type']} {snapshot['start_frame']} {mute}\n"
        sources = []
        for clip in snapshot["clips"]:
            sources.append(f"{clip['id']} {clip['media_id']} {clip['start']} {clip['end']} {clip['source_time']:.12g}\n")
        segments = [f"{part['source'] + 1} {part['in']} {part['frames']} {part['record']}\n"
                    for part in plan["segments"]]
        payload = header + "".join(sources + segments)
        if len(payload) > 250_000 or len(sources) + len(segments) > 4999:
            raise ValueError("El plan supera el tamaño de un trabajo de edición.")
        return self.mailbox.stage("audiocommit" if activate else "audioapply",
                                  snapshot["project_id"], snapshot["timeline_id"],
                                  prepare=lambda request_id: payload)


def summarize(job):
    snapshot, plan = job["snapshot"], job["plan"]
    fps = float(frame_rate(snapshot["fps"]))
    job["summary"] = {"source_clips": len(snapshot["clips"]),
                      "segments": len(plan["segments"]),
                      "input_seconds": sum(clip["end"] - clip["start"] for clip in snapshot["clips"]) / fps,
                      "output_seconds": plan["duration_frames"] / fps,
                      "review_groups": sum(group["selected_index"] == -1 for group in job["groups"]),
                      "discarded_takes": sum(len(group["takes"]) - 1 for group in job["groups"]
                                             if len(group["takes"]) > 1 and group["selected_index"] != -1)}


def run_job(path):
    job = json.loads(path.read_text(encoding="utf-8"))
    job.update(pid=os.getpid(), updated_at=time.time(), progress="Cargando modelo local")
    write_json(path, job)
    try:
        def progress(message):
            job.update(progress=message, updated_at=time.time())
            write_json(path, job)
        groups, plan = analyze_snapshot(job["snapshot"], job["options"], progress)
        job.update(status="ready", groups=groups, plan=plan, updated_at=time.time(),
                   progress="Plan listo para revisar")
        summarize(job)
    except Exception as error:
        job.update(status="error", error=str(error), updated_at=time.time())
    write_json(path, job)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", type=Path, required=True)
    run_job(parser.parse_args().job)
