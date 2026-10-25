"""Record the full Windows desktop with a persistent FFmpeg supervisor.

Usage: python -m scripts.video.record start --name escena1
       python -m scripts.video.record stop
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "video" / "hito2" / "raw"
STATE = RAW / ".recording.json"
STOP_REQUEST = RAW / ".stop-request"


def recording_command(output: Path) -> list[str]:
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-y",
        "-f",
        "gdigrab",
        "-framerate",
        "30",
        "-i",
        "desktop",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        str(output),
    ]


def _scene_name(value: str) -> str:
    if re.fullmatch(r"[a-zA-Z0-9_-]+", value) is None:
        raise ValueError("El nombre de escena solo admite letras, numeros, - y _.")
    return value


def start(name: str, *, raw: Path = RAW, timeout: float = 10.0) -> Path:
    name = _scene_name(name)
    raw.mkdir(parents=True, exist_ok=True)
    state = raw / STATE.name
    stop_request = raw / STOP_REQUEST.name
    if state.exists():
        raise RuntimeError("Ya hay una grabacion activa; usa stop antes de iniciar otra.")
    if stop_request.exists():
        stop_request.unlink()
    output = raw / f"{name}.mp4"
    if output.exists():
        raise FileExistsError(f"Ya existe {output.name}; elige otra escena.")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    with (raw / ".recording.log").open("a", encoding="utf-8") as log:
        supervisor = subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "_worker",
                "--name",
                name,
                "--raw",
                str(raw),
            ],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            creationflags=flags,
        )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if state.exists():
            return output
        if supervisor.poll() is not None:
            raise RuntimeError("FFmpeg no inicio; revisa video/hito2/raw/.recording.log.")
        time.sleep(0.1)
    raise TimeoutError("FFmpeg no confirmo el inicio; revisa el log de grabacion.")


def stop(*, raw: Path = RAW, timeout: float = 45.0) -> Path:
    state = raw / STATE.name
    if not state.exists():
        raise RuntimeError("No hay una grabacion activa.")
    data = json.loads(state.read_text(encoding="utf-8"))
    output = raw / str(data["name"] + ".mp4")
    (raw / STOP_REQUEST.name).write_text("q\n", encoding="ascii")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not state.exists():
            if output.exists() and output.stat().st_size > 0:
                return output
            raise RuntimeError("FFmpeg termino sin un MP4 valido; revisa el log de grabacion.")
        time.sleep(0.1)
    raise TimeoutError("FFmpeg sigue cerrando el MP4; no mates el proceso, reintenta stop.")


def worker(name: str, *, raw: Path = RAW) -> int:
    name = _scene_name(name)
    state = raw / STATE.name
    request = raw / STOP_REQUEST.name
    output = raw / f"{name}.mp4"
    with (raw / ".ffmpeg.log").open("a", encoding="utf-8") as log:
        process = subprocess.Popen(
            recording_command(output),
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=log,
            cwd=ROOT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        state.write_text(
            json.dumps({"name": name, "supervisor_pid": os.getpid(), "ffmpeg_pid": process.pid}),
            encoding="utf-8",
        )
        try:
            while process.poll() is None:
                if request.exists():
                    request.unlink()
                    if process.stdin is not None:
                        process.stdin.write(b"q\n")
                        process.stdin.flush()
                    break
                time.sleep(0.1)
            return process.wait()
        finally:
            state.unlink(missing_ok=True)
            request.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    begin = commands.add_parser("start")
    begin.add_argument("--name", required=True)
    commands.add_parser("stop")
    internal = commands.add_parser("_worker", help=argparse.SUPPRESS)
    internal.add_argument("--name", required=True)
    internal.add_argument("--raw", type=Path, default=RAW)
    args: Any = parser.parse_args(argv)
    try:
        if args.command == "start":
            print(f"Grabando: {start(args.name)}")
        elif args.command == "stop":
            print(f"Grabacion cerrada: {stop()}")
        else:
            return worker(args.name, raw=args.raw)
    except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
        parser.exit(1, f"Error de grabacion: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
