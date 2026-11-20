"""Normalize an agent's time-based shot selection into an editable MCPX catalog.

Requires PyAV and NumPy. The agent supplies the selection after inspecting the
source images and editorial brief. Source files are opened for reading.
"""

import argparse
from fractions import Fraction
import json
import math
from pathlib import Path


def align_to_beats(plan, analysis, max_frames=None):
    """Choose ordered beat positions nearest the existing editorial cut points."""
    from copy import deepcopy

    fps = plan["fps"]
    if analysis["fps"] != fps:
        raise ValueError("Beat analysis and montage must use the same frame rate")
    total = sum(shot["frames"] for shot in plan["shots"])
    candidates = sorted({event["frame"] for event in analysis["events"]
                         if type(event["frame"]) is int and 0 < event["frame"] < total})
    targets = []
    offset = 0
    for shot in plan["shots"][:-1]:
        offset += shot["frames"]
        targets.append(offset)
    limits = max_frames or [total] * len(plan["shots"])
    if len(limits) != len(plan["shots"]):
        raise ValueError("Provide one duration limit for each shot")
    minimum = max(1, round(fps * .35))
    states = {0: (0, [])}
    for index, target in enumerate(targets):
        next_states = {}
        for candidate in candidates:
            options = [(cost + (candidate - target) ** 2, path + [candidate])
                       for previous, (cost, path) in states.items()
                       if minimum <= candidate - previous <= limits[index]]
            if options:
                next_states[candidate] = min(options, key=lambda option: option[0])
        states = next_states
    finals = [(cost, path) for previous, (cost, path) in states.items()
              if minimum <= total - previous <= limits[-1]]
    if not finals:
        raise ValueError("No beat-aligned plan satisfies the shot duration limits")
    boundaries = [0, *min(finals, key=lambda option: option[0])[1], total]
    result = deepcopy(plan)
    for shot, start, end in zip(result["shots"], boundaries, boundaries[1:]):
        shot["frames"] = end - start
    result["beat_frames"] = candidates
    result["cut_frames"] = boundaries[1:-1]
    return result


def prepare_selection(plan, output):
    import av
    import numpy as np

    fps = plan.get("fps", 30)
    if type(fps) is not int or not 1 <= fps <= 120:
        raise ValueError("Invalid integer output frame rate")
    shots = plan["shots"]
    if not isinstance(shots, list) or not 1 <= len(shots) <= 200:
        raise ValueError("Provide between 1 and 200 shots")
    lengths = []
    for shot in shots:
        if type(shot["frames"]) is not int or shot["frames"] <= 0:
            raise ValueError("Shot duration must be positive integer frames")
        start = shot["start"]
        if type(start) not in (int, float) or not math.isfinite(start) or start < 0:
            raise ValueError("Invalid source start time")
        with av.open(str(shot["path"])) as source:
            stream = source.streams.video[0]
            duration = float(stream.duration * stream.time_base)
            if start + shot["frames"] / fps > duration:
                raise ValueError("Selection exceeds source duration")
        lengths.append(shot["frames"])

    sample_rate = 48000
    if sample_rate % fps:
        raise ValueError("Output frame rate must divide 48000")
    samples_per_frame = sample_rate // fps
    total_samples = sum(lengths) * samples_per_frame
    audio_parts = []
    count = 0
    with av.open(str(plan["music"])) as source:
        resampler = av.AudioResampler(format="fltp", layout="stereo", rate=sample_rate)
        for frame in source.decode(audio=0):
            for converted in resampler.resample(frame):
                samples = converted.to_ndarray()
                audio_parts.append(samples)
                count += samples.shape[1]
            if count >= total_samples:
                break
        if count < total_samples:
            for converted in resampler.resample(None):
                audio_parts.append(converted.to_ndarray())
    music = np.concatenate(audio_parts, axis=1)[:, :total_samples]
    if music.shape[1] < total_samples:
        raise ValueError("Music is shorter than the requested montage")
    peak = float(np.max(np.abs(music)))
    if peak:
        music *= min(1.0, .8 / peak)
    fade_in = min(int(.08 * sample_rate), total_samples)
    fade_out = min(int(.15 * sample_rate), total_samples)
    music[:, :fade_in] *= np.linspace(0, 1, fade_in)
    music[:, -fade_out:] *= np.linspace(1, 0, fade_out)
    music = (np.clip(music, -1, 1) * 32767).astype(np.int16)

    width, height = plan.get("width", 1080), plan.get("height", 1920)
    if (type(width) is not int or type(height) is not int
            or min(width, height) < 16 or max(width, height) > 8192
            or width % 2 or height % 2):
        raise ValueError("Output dimensions must be even integers between 16 and 8192")
    output.mkdir(parents=True, exist_ok=False)
    media = output / "media"
    media.mkdir()
    (output / "output").mkdir()
    catalog = {"fps": fps, "width": width, "height": height, "media": {}}
    offset = 0
    for index, (shot, length) in enumerate(zip(shots, lengths), 1):
        name = f"Shot-{index:02d}.mov"
        with av.open(str(shot["path"])) as source, av.open(str(media / name), "w") as destination:
            stream = source.streams.video[0]
            origin = float((stream.start_time or 0) * stream.time_base)
            start = origin + shot["start"]
            source.seek(int(start / stream.time_base), stream=stream, backward=True)
            decoder = source.decode(stream)
            current = next(decoder)
            following = next(decoder, None)
            video = destination.add_stream("libx264", rate=fps)
            video.width, video.height, video.pix_fmt = width, height, "yuv420p"
            video.options = {"crf": "18", "preset": "fast"}
            audio = destination.add_stream("pcm_s16le", rate=sample_rate)
            audio.layout = "stereo"
            for frame_index in range(length):
                timestamp = start + frame_index / fps
                while following is not None and following.time <= timestamp:
                    current, following = following, next(decoder, None)
                rotation = current.rotation
                if rotation not in (-270, -180, -90, 0, 90, 180, 270):
                    raise ValueError("Unsupported source rotation")
                pixels = np.rot90(current.to_ndarray(format="rgb24"), k=rotation // 90)
                if shot.get("mirror", False):
                    pixels = np.fliplr(pixels)
                frame = av.VideoFrame.from_ndarray(np.ascontiguousarray(pixels), format="rgb24")
                if frame.width * height != frame.height * width:
                    raise ValueError("Source aspect ratio differs from output")
                frame = frame.reformat(width=width, height=height, format="yuv420p")
                frame.pts, frame.time_base = frame_index, Fraction(1, fps)
                for packet in video.encode(frame):
                    destination.mux(packet)
                first_sample = (offset + frame_index) * samples_per_frame
                wave = music[:, first_sample:first_sample + samples_per_frame]
                packed = np.ascontiguousarray(wave.T).reshape(1, -1)
                sound = av.AudioFrame.from_ndarray(packed, format="s16", layout="stereo")
                sound.sample_rate = sample_rate
                sound.pts, sound.time_base = frame_index * samples_per_frame, Fraction(1, sample_rate)
                for packet in audio.encode(sound):
                    destination.mux(packet)
            for packet in video.encode():
                destination.mux(packet)
            for packet in audio.encode():
                destination.mux(packet)
        with av.open(str(media / name)) as check:
            if sum(1 for _ in check.decode(video=0)) != length:
                raise ValueError("Normalized clip frame count differs from plan")
        catalog["media"][f"S{index:02d}"] = {"file": name, "frames": length, "audio_channels": 2}
        offset += length
        print(f"Prepared {name}, {length} frames", flush=True)
    (output / "manifest.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    (output / "selection.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    prepare_selection(json.loads(args.plan.read_text(encoding="utf-8")), args.output)


if __name__ == "__main__":
    main()
