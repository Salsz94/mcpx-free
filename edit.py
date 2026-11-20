"""Frame-accurate export for a local, operator-approved media manifest."""

from fractions import Fraction
from pathlib import Path
import os
import stat
import uuid
import xml.etree.ElementTree as ET


def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"Se esperaba un entero entre {low} y {high}.")
    return value


def safe_path(root, relative):
    path = Path(relative)
    if path.anchor or not path.parts or any(
        part == ".." or ":" in part or part.endswith((" ", ".")) for part in path.parts
    ):
        raise ValueError("Se requiere una ruta relativa ordinaria.")
    candidate = root
    for part in path.parts:
        candidate /= part
        attributes = getattr(candidate.lstat(), "st_file_attributes", 0)
        if candidate.is_symlink() or attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError("Los enlaces y puntos de reanálisis están excluidos.")
    return candidate


class Editor:
    def __init__(self, media_root, output, manifest):
        self.root = media_root.resolve(strict=True)
        self.output = output.resolve(strict=True)
        if not self.root.is_dir() or not self.output.is_dir():
            raise ValueError("Las raíces de medios y salida deben ser directorios.")
        self.fps = integer(manifest["fps"], 1, 60)
        self.width = integer(manifest["width"], 1, 8192)
        self.height = integer(manifest["height"], 1, 8192)
        self.media = manifest["media"]
        if not isinstance(self.media, dict) or not self.media:
            raise ValueError("El manifiesto requiere un catálogo de medios.")
        for media in self.media.values():
            integer(media["frames"], 1, 10_000_000)
            integer(media["audio_channels"], 0, 2)
            integer(media.get("start_frame", 0), 0, 10_000_000)
            if not isinstance(media["file"], str):
                raise ValueError("El archivo de cada medio debe ser una ruta relativa.")

    def catalog(self):
        return {"fps": self.fps, "media": [
            {"id": key, "name": Path(item["file"]).name, "frames": item["frames"],
             "audio_channels": item["audio_channels"]}
            for key, item in self.media.items()
        ]}

    def plan(self, cuts):
        if not isinstance(cuts, list) or not 1 <= len(cuts) <= 200:
            raise ValueError("Se requieren entre 1 y 200 cortes.")
        offset = 0
        segments = []
        for cut in cuts:
            if not isinstance(cut, dict) or cut.keys() != {"media", "in", "out"}:
                raise ValueError("Cada corte requiere media, in y out.")
            key = cut["media"]
            if not isinstance(key, str) or key not in self.media:
                raise ValueError("Identificador de medio desconocido.")
            media = self.media[key]
            path = safe_path(self.root, media["file"])
            if not path.is_file():
                raise ValueError("El medio debe ser un archivo.")
            frames = media["frames"]
            start = integer(cut["in"], 0, frames - 1)
            end = integer(cut["out"], start + 1, frames)
            segments.append({**cut, "offset": offset, "duration": end - start})
            offset += end - start
        return {"fps": self.fps, "duration_frames": offset, "segments": segments}

    def export(self, cuts, *, directory=None, operation_id=None):
        plan = self.plan(cuts)
        name = f"MCPX-{operation_id or uuid.uuid4().hex}"
        output = directory if directory is not None else self.output

        def time(frames):
            value = Fraction(frames, self.fps)
            return f"{value}s"

        root = ET.Element("fcpxml", version="1.9")
        resources = ET.SubElement(root, "resources")
        ET.SubElement(resources, "format", id="r1", frameDuration=time(1),
                      width=str(self.width), height=str(self.height))
        refs = {}
        for segment in plan["segments"]:
            key = segment["media"]
            if key in refs:
                continue
            ref = refs[key] = f"r{len(refs) + 2}"
            media = self.media[key]
            path = safe_path(self.root, media["file"])
            channels = media["audio_channels"]
            origin = media.get("start_frame", 0)
            asset = ET.SubElement(resources, "asset", id=ref, name=path.name,
                                  start=time(origin), duration=time(media["frames"]),
                                  format="r1", hasVideo="1")
            if channels:
                asset.attrib.update(hasAudio="1", audioSources="1",
                                    audioChannels=str(channels), audioRate="48000")
            ET.SubElement(asset, "media-rep", kind="original-media", src=path.as_uri())

        event = ET.SubElement(ET.SubElement(root, "library"), "event", name="MCPX")
        project = ET.SubElement(event, "project", name=name)
        sequence = ET.SubElement(project, "sequence", format="r1",
                                 duration=time(plan["duration_frames"]), tcStart="0s",
                                 tcFormat="NDF", audioRate="48k", audioLayout="stereo")
        spine = ET.SubElement(sequence, "spine")
        for segment in plan["segments"]:
            key = segment["media"]
            origin = self.media[key].get("start_frame", 0)
            ET.SubElement(spine, "asset-clip", ref=refs[key], offset=time(segment["offset"]),
                          start=time(origin + segment["in"]), duration=time(segment["duration"]))
        ET.indent(root)
        destination = output / f"{name}.fcpxml"
        temporary = output / f".{name}.tmp"
        try:
            with temporary.open("xb") as stream:
                stream.write(b'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>\n')
                stream.write(ET.tostring(root, encoding="utf-8"))
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        ET.parse(destination)
        return {"status": "exported", "path": str(destination), **plan}
