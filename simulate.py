"""Run the actual stdio server and Lua bridge against an isolated simulated timeline."""
import ctypes
from fractions import Fraction
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlparse
from urllib.request import url2pathname
import xml.etree.ElementTree as ET

from smoke import Client

ROOT = Path(__file__).resolve().parent
DLL = Path("C:/Program Files/Blackmagic Design/DaVinci Resolve/lua5.1.dll")


def main():
    lua = ctypes.CDLL(str(DLL))
    ptr = ctypes.c_void_p
    lua.luaL_newstate.restype = ptr
    lua.luaL_openlibs.argtypes = [ptr]
    lua.luaL_loadstring.argtypes = [ptr, ctypes.c_char_p]
    lua.lua_pcall.argtypes = [ptr, ctypes.c_int, ctypes.c_int, ctypes.c_int]
    lua.lua_tolstring.argtypes = [ptr, ctypes.c_int, ptr]
    lua.lua_tolstring.restype = ctypes.c_char_p
    lua.lua_close.argtypes = [ptr]
    state = lua.luaL_newstate()
    lua.luaL_openlibs(state)

    def run(code):
        if lua.luaL_loadstring(state, code.encode()) or lua.lua_pcall(state, 0, 0, 0):
            raise RuntimeError(lua.lua_tolstring(state, -1, None))

    try:
        with TemporaryDirectory() as directory:
            base = Path(directory)
            media = {}
            for name in "ABC":
                (base / (name + ".mov")).touch()
                media[name] = dict(file=name + ".mov", frames=180, audio_channels=1)
            manifest = base / "manifest.json"
            manifest.write_text(json.dumps(dict(fps=30, width=320, height=240, media=media)))
            for name in ("lock", "request.txt", "response.txt"):
                (base / name).write_bytes(b"0" if name == "lock" else b"")
            run((ROOT / "simulate_host.lua").read_text())
            run("MCPX_DIRECTORY=" + json.dumps(base.as_posix()))
            dispatch = "dofile(" + json.dumps((ROOT / "bridge.lua").as_posix()) + ")"
            with Client(["--session", directory, "--manifest", str(manifest),
                         "--media-root", directory, "--output", directory]) as client:
                def result(token):
                    return client.call("resolve_result", request_id=token)["status"]

                def stage(tool, **args):
                    token = client.call(tool, **args)["request_id"]
                    assert result(token) == "pending_operator"
                    return token

                token = stage("request_inspection")
                run(dispatch)
                assert result(token) == "read_from_resolve"
                target = dict(project_id="project", timeline_id="timeline")
                cuts = [{"media": k, "in": a, "out": b} for k, a, b in
                        [("B", 60, 180), ("A", 30, 120), ("C", 0, 150)]]
                token = stage("request_assembly", cuts=cuts, **target)
                xml = ET.parse(base / f"MCPX-{token}.fcpxml")
                paths = {a.get("id"): Path(url2pathname(urlparse(a.find("media-rep").get("src")).path)).as_posix()
                         for a in xml.findall(".//asset")}
                run("xmlClips={}; simulatedTrack=1; timelineName=" + json.dumps("MCPX-" + token))
                for clip in xml.findall(".//asset-clip"):
                    offset, duration, source = [Fraction(clip.get(k)[:-1]) * 30 for k in ("offset", "duration", "start")]
                    run("table.insert(xmlClips,{path=" + json.dumps(paths[clip.get("ref")]) +
                        f",offset={offset},duration={duration},source={source}" + "})")
                run(dispatch)
                assert result(token) == "verified_import"
                run(dispatch)
                assert result(token) == "verified_import"
                run("missingAudio=2")
                run(dispatch)
                assert result(token) == "resolve_error"
                run("missingAudio=nil; simulatedTrack=2")
                run(dispatch)
                assert result(token) == "resolve_error", "Montaje en pistas incorrectas aceptado"
                token = stage("request_timeline")
                run(dispatch)
                snapshot = client.call("resolve_result", request_id=token)
                assert snapshot["analysis"]["tracks"] == {"V2": 3, "A2": 3}
                assert snapshot["analysis"]["gaps"]["count"] == 0
                assert len(snapshot["clips"]) == 6
                token = stage("request_test_marker", frame=120, **target)
                for _ in range(2):
                    run(dispatch)
                    assert result(token) == "verified_in_timeline"
                token = stage("request_test_marker", frame=120, **target)
                run(dispatch)
                assert result(token) == "resolve_error"
                token = stage("request_test_marker", frame=121, project_id="stale", timeline_id="timeline")
                run(dispatch)
                assert result(token) == "resolve_error"
                token = stage("request_test_marker", frame=122, **target)
                run("MCPX_BRIDGE_SCRIPT=" + json.dumps((ROOT / "bridge.lua").as_posix()))
                run("dofile(" + json.dumps((ROOT / "worker.lua").as_posix()) + ")")
                assert result(token) == "verified_in_timeline"
                run("dofile(" + json.dumps((ROOT / "worker.lua").as_posix()) + ")")
                assert result(token) == "verified_in_timeline"
                print("Consulta, montaje, repetición, audio ausente, marcador, colisión y proyecto obsoleto: OK")
    finally:
        lua.lua_close(state)


if __name__ == "__main__":
    main()
