"""Single-slot mailbox with explicit operator dispatch in Resolve."""

from contextlib import contextmanager
from pathlib import Path
import os
import re
import time
import uuid

from edit import integer, safe_path
from vendor.creative_editor.analysis import analyze


IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,100}")
REQUEST_ID = re.compile(r"[0-9a-f]{32}")


class Mailbox:
    def __init__(self, directory):
        self.directory = directory.resolve(strict=True)
        for name in ("request.txt", "response.txt", "lock"):
            if not safe_path(self.directory, name).is_file():
                raise ValueError(f"Falta el archivo de sesión {name}.")

    def path(self, name):
        return safe_path(self.directory, name)

    def current(self):
        fields = self.path("request.txt").read_text(encoding="ascii").splitlines()
        if not fields:
            return []
        header = fields[0].split()
        if (len(header) != 6 or not REQUEST_ID.fullmatch(header[0])
                or not header[1].isdigit()):
            raise ValueError("Cabecera del buzón dañada. Conserve los archivos y revise Resolve antes de crear otra sesión.")
        return header

    @contextmanager
    def lock(self):
        with self.path("lock").open("r+b") as stream:
            if os.name == "nt":
                import msvcrt
                try:
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError as exc:
                    raise ValueError("Otro cliente está publicando una solicitud.") from exc
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield

    def stage(self, operation, project="-", timeline="-", frame=0, prepare=None):
        if any(not isinstance(value, str) or not IDENTIFIER.fullmatch(value)
               for value in (project, timeline)):
            raise ValueError("Identificador de proyecto o timeline inválido.")
        integer(frame, 0, 10_000_000)
        with self.lock():
            previous = self.current()
            if previous and int(previous[1]) >= time.time() and not self.read(previous[0]):
                raise ValueError(f"Hay una solicitud pendiente: {previous[0]}.")
            request_id = uuid.uuid4().hex
            expires = int(time.time()) + 120
            temporary = self.directory / (request_id + ".tmp")
            try:
                payload = prepare(request_id) if prepare else ""
                with temporary.open("xb") as stream:
                    stream.write(f"{request_id} {expires} {operation} {project} {timeline} {frame}\n".encode("ascii"))
                    stream.write(payload.encode("ascii"))
                os.replace(temporary, self.path("request.txt"))
            finally:
                temporary.unlink(missing_ok=True)
        return {"status": "pending_operator", "request_id": request_id, "expires_at": expires}

    def stage_import(self, editor, project, timeline, cuts):
        plan = editor.plan(cuts)
        expected = []
        for segment in plan["segments"]:
            media = editor.media[segment["media"]]
            if media.get("start_frame", 0):
                raise ValueError("El montaje mediante Lua requiere origen de medio en el fotograma cero.")
            path = safe_path(editor.root, media["file"]).as_posix().encode("utf-8").hex()
            expected.append(f"{path} {segment['offset']} {segment['duration']} {segment['in']} {media['audio_channels']}\n")
        payload = "".join(expected)
        if len(payload) > 260_000:
            raise ValueError("El plan supera el tamaño de la solicitud Lua.")

        def prepare(request_id):
            editor.export(cuts, directory=self.directory, operation_id=request_id)
            return payload

        return self.stage("assemble", project, timeline, editor.fps, prepare)

    def read(self, request_id):
        if not isinstance(request_id, str) or not REQUEST_ID.fullmatch(request_id):
            raise ValueError("Identificador de solicitud inválido.")
        try:
            with self.path("response.txt").open("rb") as stream:
                line = stream.readline(262_145)
        except PermissionError:
            return None
        if len(line) > 262_144:
            if line.startswith(request_id.encode("ascii") + b"|"):
                raise ValueError("La respuesta supera 256 KiB. Inspeccione una timeline menor en Resolve.")
            return None
        if not line.endswith(b"\n"):
            return None
        fields = line.rstrip(b"\r\n").split(b"|")
        if len(fields) < 4 or fields[0] != request_id.encode("ascii") or fields[-1] != b"END":
            return None
        values = [bytes.fromhex(field.decode("ascii")).decode("utf-8", "replace")
                  for field in fields[2:-1]]
        if fields[1] == b"ok" and values and values[0] == "snapshot":
            if len(values) < 6 or (len(values) - 6) % 8:
                raise ValueError("Lectura de clips incompleta.")
            items = []
            for index in range(6, len(values), 8):
                kind, track, clip_id, name, start, end, source, path = values[index:index + 8]
                items.append(dict(track_type=kind, track=int(track), id=clip_id, name=name,
                                  start=int(start), end=int(end), source_start=float(source), path=path))
            return dict(status="read_from_resolve", project_id=values[1], timeline_id=values[2],
                        fps=values[3], start_frame=int(values[4]), end_frame=int(values[5]),
                        clips=items, analysis=analyze(items))
        if fields[1] == b"error":
            return {"status": "resolve_error", "message": values[0]}
        if fields[1] == b"ok" and len(values) == 3:
            return {"status": "verified_in_timeline", "timeline_id": values[0],
                    "frame": int(values[1]), "marker": values[2]}
        if fields[1] == b"ok" and len(values) == 4:
            return {"status": "verified_import", "timeline_id": values[0],
                    "timeline": values[1], "duration_frames": int(values[2]),
                    "video_clips": int(values[3])}
        if fields[1] == b"ok" and len(values) >= 5 and len(values) % 2 == 1:
            edition = {"DaVinci Resolve": "free", "DaVinci Resolve Studio": "studio"}.get(values[0], "unknown")
            return {"status": "read_from_resolve", "product": values[0], "edition": edition, "version": values[1],
                    "project": values[2], "project_id": values[3], "active_timeline": values[4],
                    "timelines": [{"id": key, "name": name}
                                  for key, name in zip(values[5::2], values[6::2])]}
        raise ValueError("Respuesta de Resolve inválida.")

    def result(self, request_id):
        result = self.read(request_id)
        if result:
            return result
        current = self.current()
        if current and current[0] == request_id and int(current[1]) >= time.time():
            return {"status": "pending_operator", "request_id": request_id}
        raise ValueError("Respuesta no disponible. Revise la timeline antes de repetir una edición.")
