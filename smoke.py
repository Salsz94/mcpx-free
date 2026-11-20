"""Drive a real MCP stdio subprocess for reproducible local checks."""

import argparse
import json
from pathlib import Path
import subprocess
import sys


class Client:
    def __init__(self, options=()):
        self.command = [sys.executable, str(Path(__file__).with_name("server.py")), *options]
        self.sequence = 0

    def __enter__(self):
        self.process = subprocess.Popen(self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        text=True, encoding="utf-8")
        try:
            self.request("initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                                        "clientInfo": {"name": "mcpx-smoke", "version": "1"}})
            self.send({"method": "notifications/initialized"})
        except BaseException:
            self.__exit__()
            raise
        return self

    def __exit__(self, *exception):
        self.process.stdin.close()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.process.stdout.close()

    def send(self, message):
        self.process.stdin.write(json.dumps({"jsonrpc": "2.0", **message}) + "\n")
        self.process.stdin.flush()

    def request(self, method, params=None):
        self.sequence += 1
        self.send({"method": method, "id": self.sequence, "params": params or {}})
        response = json.loads(self.process.stdout.readline())
        if response.get("id") != self.sequence or "result" not in response:
            raise RuntimeError(response)
        return response["result"]

    def call(self, name, **arguments):
        result = self.request("tools/call", {"name": name, "arguments": arguments})
        return json.loads(result["content"][0]["text"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session")
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("tool")
    parser.add_argument("arguments", nargs="?", default="{}")
    args = parser.parse_args()
    options = ["--session", args.session] if args.session else []
    if args.fixture:
        for flag, path in (("--media-root", "media"), ("--manifest", "manifest.json"),
                           ("--output", "output")):
            options.extend([flag, str(args.fixture / path)])
    with Client(options) as client:
        result = client.call(args.tool, **json.loads(args.arguments))
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return int(result.get("status") in {"error", "resolve_error"})


if __name__ == "__main__":
    sys.exit(main())
