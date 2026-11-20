"""Optional live-test fixtures using PyAV and NumPy."""

import json
from pathlib import Path
import sys

import av
import numpy as np


def main(root):
    root.mkdir()
    media = root / "media"
    media.mkdir()
    (root / "output").mkdir()
    manifest = {"fps": 30, "width": 320, "height": 240, "media": {}}
    for index, key in enumerate("ABC"):
        filename = f"{key} sample.mov"
        with av.open(str(media / filename), "w") as container:
            video = container.add_stream("libx264", rate=30)
            video.width, video.height, video.pix_fmt = 320, 240, "yuv420p"
            audio = container.add_stream("pcm_s16le", rate=48000)
            audio.layout = "mono"
            for frame in range(180):
                pixels = np.zeros((240, 320, 3), dtype=np.uint8)
                pixels[:, :, index] = 200
                pixels[:, frame:frame + 8] = 255
                for packet in video.encode(av.VideoFrame.from_ndarray(pixels, format="rgb24")):
                    container.mux(packet)
                phase = np.arange(frame * 1600, (frame + 1) * 1600)
                wave = (5000 * np.sin(2 * np.pi * (440 + 110 * index) * phase / 48000))
                chunk = av.AudioFrame.from_ndarray(wave.astype(np.int16)[None, :], format="s16", layout="mono")
                chunk.sample_rate = 48000
                for packet in audio.encode(chunk):
                    container.mux(packet)
            for stream in (video, audio):
                for packet in stream.encode():
                    container.mux(packet)
        manifest["media"][key] = {"file": filename, "frames": 180, "audio_channels": 1}
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
