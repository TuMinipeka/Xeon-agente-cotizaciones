"""Rebuild the original stereo soundscape against the current scene timing."""

from __future__ import annotations

import json
import math
import random
import struct
import subprocess
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TIMING = json.loads((ROOT / "src" / "timing-v3.json").read_text(encoding="utf-8"))
SCENES = TIMING["scenes"]
OUT_DIR = ROOT / "public" / "sound"
OUT_DIR.mkdir(parents=True, exist_ok=True)

rate = 24_000
duration = TIMING["duration"]
chords = [
    (110.00, 130.81, 164.81),
    (98.00, 123.47, 146.83),
    (130.81, 164.81, 196.00),
    (110.00, 146.83, 174.61),
    (98.00, 130.81, 164.81),
    (130.81, 164.81, 220.00),
    (110.00, 164.81, 220.00),
]
chime_times = [SCENES[index]["start"] + 5.2 for index in (2, 4, 5)]
transitions = [scene["start"] for scene in SCENES[1:]]
rng = random.Random(50)
wav_path = OUT_DIR / "soundscape.wav"


def chord(notes: tuple[float, float, float], phase: float, time: float) -> float:
    return (
        sum(
            math.sin(2 * math.pi * frequency * time + phase + index * 0.6)
            for index, frequency in enumerate(notes)
        )
        / 3
    )


with wave.open(str(wav_path), "wb") as output:
    output.setnchannels(2)
    output.setsampwidth(2)
    output.setframerate(rate)
    chunk = bytearray()
    scene_index = 0
    for sample in range(math.ceil(duration * rate)):
        t = sample / rate
        while scene_index + 1 < len(SCENES) and t >= SCENES[scene_index + 1]["start"]:
            scene_index += 1
        current = chords[scene_index]
        previous = chords[max(scene_index - 1, 0)]
        blend = min(1.0, max(0.0, (t - SCENES[scene_index]["start"]) / 1.6))
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
print(f"Soundscape sincronizado: {duration:.3f} s; {len(SCENES)} escenas.")
