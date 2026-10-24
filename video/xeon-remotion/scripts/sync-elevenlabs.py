"""Sync the approved ElevenLabs take to XEON's scene and caption timeline."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = json.loads((ROOT / "narration-script.json").read_text(encoding="utf-8"))

# Speech boundaries measured from the single Bella / Multilingual v2 take.
# The short pauses inside some lines are intentionally kept within that line.
BOUNDARIES = [
    (0.000, 3.260),
    (3.744, 7.317),
    (7.867, 11.189),
    (11.605, 14.060),
    (14.472, 16.543),
    (17.169, 21.096),
    (21.602, 25.435),
    (25.986, 28.487),
    (29.031, 31.775),
    (32.105, 35.510),
    (36.059, 38.557),
    (39.038, 43.764),
    (44.255, 47.028),
    (47.725, 50.140),
    (50.658, 54.126),
    (54.691, 58.660),
    (59.252, 62.305),
    (62.944, 65.775),
    (66.316, 70.199),
    (70.782, 76.634),
    (77.062, 80.588),
]
LEAD = 0.48
AUDIO_DURATION = 80.927


def timestamp(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


script_lines = [line for scene in SCRIPT["scenes"] for line in scene["lines"]]
assert len(script_lines) == len(BOUNDARIES) == 21

captions = [
    {"start": round(start + LEAD, 3), "end": round(end + LEAD, 3), "text": text}
    for text, (start, end) in zip(script_lines, BOUNDARIES, strict=True)
]

scenes = []
line_index = 0
for scene in SCRIPT["scenes"]:
    count = len(scene["lines"])
    start = round(BOUNDARIES[line_index][0], 3)
    end = (
        round(BOUNDARIES[line_index + count][0], 3)
        if line_index + count < len(BOUNDARIES)
        else round(AUDIO_DURATION + 0.8, 3)
    )
    scenes.append(
        {
            "id": scene["id"],
            "label": scene["label"],
            "start": start,
            "end": end,
            "lines": captions[line_index : line_index + count],
        }
    )
    line_index += count

timing = {"scenes": scenes, "captions": captions, "duration": scenes[-1]["end"]}
(ROOT / "src" / "timing-v3.json").write_text(
    json.dumps(timing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
(ROOT / "subtitles-v3.srt").write_text(
    "\n".join(
        f"{index}\n{timestamp(item['start'])} --> {timestamp(item['end'])}\n{item['text']}\n"
        for index, item in enumerate(captions, 1)
    ),
    encoding="utf-8",
)
print(f"Sincronizadas {len(captions)} líneas y {len(scenes)} escenas; {timing['duration']:.3f} s.")
