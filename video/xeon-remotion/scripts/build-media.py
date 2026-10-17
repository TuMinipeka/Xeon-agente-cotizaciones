"""Assemble local narration, timed captions, and a generated stereo soundscape."""

from __future__ import annotations

import json
import math
import random
import struct
import subprocess
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = json.loads((ROOT / "narration-script.json").read_text(encoding="utf-8"))
VOICE_DIR = ROOT / "public" / "voice-local"
OUT_DIR = ROOT / "public" / "sound"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def timestamp(seconds: float) -> str:
    millis = round(seconds * 1000)
    hours, rem = divmod(millis, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{ms:03}"


scenes: list[dict] = []
captions: list[dict] = []
voice_path = VOICE_DIR / "narration.wav"
line_index = 0

with wave.open(str(VOICE_DIR / "lines" / "00.wav"), "rb") as first:
    params = first.getparams()
rate = params.framerate
assert params.nchannels == 1 and params.sampwidth == 2

with wave.open(str(voice_path), "wb") as output:
    output.setparams(params)
    written = 0

    def silence(seconds: float) -> None:
        global written
        count = round(seconds * rate)
        output.writeframes(b"\0\0" * count)
        written += count

    for scene in SCRIPT["scenes"]:
        scene_start = written / rate
        silence(0.48)
        scene_lines: list[dict] = []
        for text in scene["lines"]:
            line_path = VOICE_DIR / "lines" / f"{line_index:02}.wav"
            with wave.open(str(line_path), "rb") as source:
                assert (
                    source.getnchannels(),
                    source.getsampwidth(),
                    source.getframerate(),
                    source.getcomptype(),
                ) == (params.nchannels, params.sampwidth, params.framerate, params.comptype), (
                    line_path
                )
                start = written / rate
                frames = source.readframes(source.getnframes())
                output.writeframes(frames)
                written += source.getnframes()
                end = written / rate
            line = {"start": round(start, 3), "end": round(end, 3), "text": text}
            scene_lines.append(line)
            captions.append(line)
            silence(0.18)
            line_index += 1
        silence(0.82)
        scenes.append(
            {
                "id": scene["id"],
                "label": scene["label"],
                "start": round(scene_start, 3),
                "end": round(written / rate, 3),
                "lines": scene_lines,
            }
        )

timing = {"scenes": scenes, "captions": captions, "duration": scenes[-1]["end"]}
(ROOT / "src" / "timing-v3.json").write_text(
    json.dumps(timing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)

srt = "\n".join(
    f"{index}\n{timestamp(caption['start'])} --> {timestamp(caption['end'])}\n{caption['text']}\n"
    for index, caption in enumerate(captions, 1)
)
(ROOT / "subtitles-v3.srt").write_text(srt, encoding="utf-8")

# A restrained, original sound bed: slowly changing minor chords, a low pulse,
# stereo transition sweeps and three confirming chimes. No samples or services.
sound_rate = 24_000
duration = timing["duration"]
chords = [
    (110.00, 130.81, 164.81),
    (98.00, 123.47, 146.83),
    (130.81, 164.81, 196.00),
    (110.00, 146.83, 174.61),
    (98.00, 130.81, 164.81),
    (130.81, 164.81, 220.00),
    (110.00, 164.81, 220.00),
]
chime_times = [scenes[i]["start"] + 5.2 for i in (2, 4, 5)]
transitions = [scene["start"] for scene in scenes[1:]]
rng = random.Random(50)
wav_path = OUT_DIR / "soundscape.wav"

with wave.open(str(wav_path), "wb") as output:
    output.setnchannels(2)
    output.setsampwidth(2)
    output.setframerate(sound_rate)
    chunk = bytearray()
    scene_index = 0
    for sample in range(math.ceil(duration * sound_rate)):
        t = sample / sound_rate
        while scene_index + 1 < len(scenes) and t >= scenes[scene_index + 1]["start"]:
            scene_index += 1
        current = chords[scene_index]
        previous = chords[max(scene_index - 1, 0)]
        blend = min(1.0, max(0.0, (t - scenes[scene_index]["start"]) / 1.6))

        def chord(notes: tuple[float, float, float], phase: float, time: float) -> float:
            return (
                sum(
                    math.sin(2 * math.pi * frequency * time + phase + index * 0.6)
                    for index, frequency in enumerate(notes)
                )
                / 3
            )

        left_pad = chord(previous, 0.05, t) * (1 - blend) + chord(current, 0.05, t) * blend
        right_pad = chord(previous, 0.65, t) * (1 - blend) + chord(current, 0.65, t) * blend
        shimmer = math.sin(2 * math.pi * 0.19 * t) * 0.006
        pulse_phase = t % 1.36
        pulse = math.sin(2 * math.pi * 55 * t) * math.exp(-pulse_phase * 7) * 0.019
        left = left_pad * (0.047 + shimmer) + pulse
        right = right_pad * (0.047 - shimmer) + pulse

        for start in transitions:
            distance = t - start
            if -0.24 < distance < 0.53:
                envelope = math.sin(math.pi * (distance + 0.24) / 0.77) ** 2
                noise = rng.uniform(-1, 1) * 0.026 * envelope
                pan = (distance + 0.24) / 0.77
                left += noise * (1 - pan)
                right += noise * pan

        for start in chime_times:
            elapsed = t - start
            if 0 <= elapsed < 1.3:
                chime = (
                    (
                        math.sin(2 * math.pi * 659.25 * elapsed)
                        + 0.4 * math.sin(2 * math.pi * 987.77 * elapsed)
                    )
                    * math.exp(-elapsed * 5)
                    * 0.039
                )
                left += chime * 0.75
                right += chime

        fade_in = min(1.0, t / 1.3)
        fade_out = min(1.0, max(0.0, (duration - t) / 1.5))
        left *= fade_in * fade_out
        right *= fade_in * fade_out
        chunk.extend(
            struct.pack(
                "<hh",
                round(max(-1, min(1, left)) * 32767),
                round(max(-1, min(1, right)) * 32767),
            )
        )
        if len(chunk) >= 32_768:
            output.writeframes(chunk)
            chunk.clear()
    if chunk:
        output.writeframes(chunk)

subprocess.run(
    [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(wav_path),
        "-q:a",
        "3",
        str(OUT_DIR / "soundscape.mp3"),
    ],
    check=True,
)
wav_path.unlink()
print(f"Narración: {duration:.2f} s; {len(captions)} líneas; 7 escenas.")
