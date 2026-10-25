"""Assemble marked screen recordings, narration, titles and burned subtitles."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "video" / "hito2"
OUTPUT_NAME = "XEON_HITO2_demo"
SCENES = ("portada", "escena1", "escena2", "escena3", "escena4", "cierre")
BACKGROUND = "0x071B19"
ACCENT = "0x00D9A3"
FONT = (
    r"fontfile='C\:/Windows/Fonts/arial.ttf'"
    if Path("C:/Windows/Fonts/arial.ttf").exists()
    else "font=Arial"
)


@dataclass(frozen=True)
class EditPlan:
    commands: tuple[tuple[str, ...], ...]
    subtitle: str
    concat_list: str
    output: Path
    srt: Path
    work: Path


def timestamp(seconds: float) -> str:
    total = round(seconds * 1000)
    hours, remainder = divmod(total, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def _text(value: str) -> str:
    return value.replace("\\", r"\\").replace(":", r"\:").replace("'", r"\'").replace("%", r"\%")


def _drawtext(
    value: str,
    *,
    size: int,
    y: str,
    x: str = "(w-text_w)/2",
    border: int = 16,
) -> str:
    return (
        f"drawtext={FONT}:text='{_text(value)}':fontcolor={ACCENT}:"
        f"fontsize={size}:box=1:boxcolor={BACKGROUND}@0.8:boxborderw={border}:"
        f"x={x}:y={y}"
    )


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _clip_command(
    source: str,
    target: str,
    start: float,
    duration: float,
    filters: list[str],
    blurs: list[tuple[int, int, int, int, float, float]],
) -> tuple[str, ...]:
    filter_args: tuple[str, ...]
    if blurs:
        base_filters = ",".join(filters[:5])
        overlays = ",".join(filters[5:])
        graph = [f"[0:v]{base_filters},split=2[base0][crop0]"]
        for index, (x, y, width, height, blur_start, blur_end) in enumerate(blurs):
            graph.append(
                f"[crop{index}]crop={width}:{height}:{x}:{y},boxblur=20:2:10:2[blur{index}]"
            )
            graph.append(
                f"[base{index}][blur{index}]overlay={x}:{y}:"
                f"enable='between(t,{blur_start:.3f},{blur_end:.3f})'[out{index}]"
            )
            if index + 1 < len(blurs):
                graph.append(f"[out{index}]split=2[base{index + 1}][crop{index + 1}]")
        if overlays:
            graph.append(f"[out{len(blurs) - 1}]{overlays}[v]")
        else:
            graph.append(f"[out{len(blurs) - 1}]null[v]")
        filter_args = ("-filter_complex", ";".join(graph), "-map", "[v]")
    else:
        filter_args = ("-vf", ",".join(filters))
    return (
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-y",
        "-ss",
        f"{start:.3f}",
        "-t",
        f"{duration:.3f}",
        "-i",
        source,
        *filter_args,
        "-an",
        "-r",
        "30",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        target,
    )


def _title_command(target: str, text: str, duration: float) -> tuple[str, ...]:
    return (
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c={BACKGROUND}:s=1920x1080:r=30:d={duration:.3f}",
        "-vf",
        _drawtext(text, size=68, y="(h-text_h)/2"),
        "-t",
        f"{duration:.3f}",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        target,
    )


def _scene_parts(mark: dict[str, Any]) -> list[tuple[float, float, float]]:
    start, end = mark.get("start"), mark.get("end")
    if not isinstance(start, (int, float)) or not isinstance(end, (int, float)) or end <= start:
        raise ValueError(f"Completa inicio y fin de {mark.get('id', 'escena')} en marks.json.")
    cursor = float(start)
    parts: list[tuple[float, float, float]] = []
    waits = sorted(mark.get("speedups", []), key=lambda wait: wait["start"])
    for wait in waits:
        wait_start, wait_end = float(wait["start"]), float(wait["end"])
        factor = float(wait.get("factor", 8))
        if factor != 8 or wait_start < cursor or wait_end > end or wait_end <= wait_start:
            raise ValueError("Las esperas deben estar dentro de la escena, sin solaparse y a x8.")
        if wait_start > cursor:
            parts.append((cursor, wait_start, 1))
        parts.append((wait_start, wait_end, 8))
        cursor = wait_end
    if cursor < end:
        parts.append((cursor, float(end), 1))
    return parts


def _part_blurs(
    marks: list[dict[str, Any]], start: float, end: float, speed: float
) -> list[tuple[int, int, int, int, float, float]]:
    active: list[tuple[int, int, int, int, float, float]] = []
    for mark in marks:
        try:
            x, y, width, height = (int(mark[key]) for key in ("x", "y", "w", "h"))
            blur_start, blur_end = float(mark["start"]), float(mark["end"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Difuminado invalido en marks.json.") from exc
        if (
            x < 0
            or y < 0
            or width <= 0
            or height <= 0
            or x + width > 1920
            or y + height > 1080
            or blur_end <= blur_start
        ):
            raise ValueError("Difuminado fuera de la imagen o con tiempo invalido.")
        overlap_start, overlap_end = max(start, blur_start), min(end, blur_end)
        if overlap_end > overlap_start:
            active.append(
                (
                    x,
                    y,
                    width,
                    height,
                    (overlap_start - start) / speed,
                    (overlap_end - start) / speed,
                )
            )
    return active


def build_plan(base: Path = BASE) -> EditPlan:
    marks = json.loads((base / "marks.json").read_text(encoding="utf-8"))
    narration = json.loads((base / "narration.json").read_text(encoding="utf-8"))
    durations = json.loads((base / "narration_durations.json").read_text(encoding="utf-8"))
    scripts = {item["id"]: item for item in narration["segments"]}
    clips = {item["id"]: item for item in durations["clips"]}
    marked = {item["id"]: item for item in marks["scenes"]}
    if set(scripts) != set(SCENES) or set(clips) != set(SCENES) or set(marked) != set(SCENES[1:-1]):
        raise ValueError("Marcas y narracion deben cubrir portada, escenas 1-4 y cierre.")

    root = base.parent.parent
    work = base / "work"
    output = base / f"{OUTPUT_NAME}.mp4"
    srt = base / f"{OUTPUT_NAME}.srt"
    commands: list[tuple[str, ...]] = []
    pieces: list[str] = []
    subtitles: list[str] = []
    timeline = 0.0
    starts: list[float] = []
    audio_inputs: list[str] = []

    for index, identifier in enumerate(SCENES, start=1):
        clip = clips[identifier]
        script = scripts[identifier]
        narration_duration = float(clip["duration"])
        if narration_duration <= 0:
            raise ValueError(f"Duracion invalida para {identifier}.")
        audio_path = base / str(clip["file"])
        if not audio_path.resolve().is_relative_to(base.resolve()):
            raise ValueError("Los clips de narracion deben estar dentro de video/hito2.")
        audio_inputs.extend(("-i", _relative(audio_path, root)))

        if identifier in {"portada", "cierre"}:
            length = max(10.0 if identifier == "portada" else 6.0, narration_duration + 1.0)
            target = work / f"{identifier}.mp4"
            commands.append(_title_command(_relative(target, root), str(script["title"]), length))
            pieces.append(target.name)
        else:
            mark = marked[identifier]
            source = base / "raw" / str(mark["file"])
            if not source.resolve().is_relative_to((base / "raw").resolve()):
                raise ValueError("El archivo de escena debe estar dentro de raw/.")
            parts = _scene_parts(mark)
            visual_duration = sum((end - start) / speed for start, end, speed in parts)
            padding = max(0.0, narration_duration + 1.0 - visual_duration)
            length = visual_duration + padding
            labels = script.get("labels", [script["title"]])
            for part_index, (start, end, speed) in enumerate(parts, start=1):
                filters = [
                    "scale=1920:1080:force_original_aspect_ratio=decrease",
                    "pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
                    "setsar=1",
                    f"setpts=(PTS-STARTPTS)/{speed:g}",
                    "fps=30",
                ]
                for label_index, label in enumerate(labels):
                    filters.append(_drawtext(str(label), size=42, y=str(35 + 72 * label_index)))
                if speed == 8:
                    filters.append(
                        _drawtext(
                            "espera acortada",
                            size=30,
                            x="w-text_w-40",
                            y="190",
                            border=10,
                        )
                    )
                if part_index == len(parts) and padding:
                    filters.append(f"tpad=stop_mode=clone:stop_duration={padding:.3f}")
                target = work / f"{identifier}-{part_index:02}.mp4"
                commands.append(
                    _clip_command(
                        _relative(source, root),
                        _relative(target, root),
                        start,
                        end - start,
                        filters,
                        _part_blurs(
                            [*marks.get("blur", []), *mark.get("blur", [])], start, end, speed
                        ),
                    )
                )
                pieces.append(target.name)

        sub_start = timeline + 0.25
        sub_end = timeline + min(length - 0.25, narration_duration + 0.25)
        starts.append(sub_start)
        subtitles.append(
            f"{index}\n{timestamp(sub_start)} --> {timestamp(sub_end)}\n{script['text']}\n"
        )
        timeline += length

    concat = "".join(f"file '{piece}'\n" for piece in pieces)
    silent = work / "silent.mp4"
    commands.append(
        (
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            _relative(work / "concat.txt", root),
            "-c",
            "copy",
            _relative(silent, root),
        )
    )
    delayed = [
        f"[{index}:a]adelay={round(start * 1000)}:all=1[a{index}]"
        for index, start in enumerate(starts, start=1)
    ]
    mix_inputs = "".join(f"[a{index}]" for index in range(1, len(SCENES) + 1))
    audio_filter = ";".join(
        [
            *delayed,
            f"{mix_inputs}amix=inputs=6:duration=longest:normalize=0,"
            "aformat=channel_layouts=mono,"
            "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[a]",
        ]
    )
    subtitle_path = _relative(srt, root).replace(":", r"\:")
    commands.append(
        (
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-y",
            "-i",
            _relative(silent, root),
            *audio_inputs,
            "-filter_complex",
            audio_filter,
            "-map",
            "0:v:0",
            "-map",
            "[a]",
            "-vf",
            f"subtitles={subtitle_path}:charenc=UTF-8",
            "-t",
            f"{timeline:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-ac",
            "1",
            _relative(output, root),
        )
    )
    return EditPlan(tuple(commands), "\n".join(subtitles), concat, output, srt, work)


def execute(plan: EditPlan, *, dry_run: bool = False) -> None:
    if dry_run:
        for command in plan.commands:
            print(subprocess.list2cmdline(command))
        return
    plan.work.mkdir(parents=True, exist_ok=True)
    plan.srt.write_text(plan.subtitle, encoding="utf-8")
    (plan.work / "concat.txt").write_text(plan.concat_list, encoding="utf-8")
    for command in plan.commands:
        subprocess.run(command, cwd=plan.work.parent.parent.parent, check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=BASE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        plan = build_plan(args.base)
        execute(plan, dry_run=args.dry_run)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Error de edicion: {exc}\n")
    if not args.dry_run:
        print(f"Video: {plan.output}\nSubtitulos: {plan.srt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
