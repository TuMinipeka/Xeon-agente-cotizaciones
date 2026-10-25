"""Generate cached ElevenLabs narration clips and measured durations."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "video" / "hito2"
SCRIPT = BASE / "narration.json"
KEY_FILE = ROOT / "secrets" / "elevenlabs_api_key.txt"
API_BASE = "https://api.elevenlabs.io/v1"
MODEL = "eleven_multilingual_v2"


def require_key(path: Path = KEY_FILE) -> str:
    try:
        key = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError("Falta secrets/elevenlabs_api_key.txt; crea el archivo local.") from exc
    if not key:
        raise RuntimeError("secrets/elevenlabs_api_key.txt esta vacio.")
    return key


def load_segments(path: Path) -> list[dict[str, str]]:
    if path.suffix.casefold() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        segments = data["segments"] if isinstance(data, dict) else data
        if not isinstance(segments, list):
            raise ValueError("La narracion JSON debe contener una lista de tramos.")
    else:
        segments = [{"id": path.stem, "title": path.stem, "text": path.read_text(encoding="utf-8")}]
    result: list[dict[str, str]] = []
    for segment in segments:
        if not isinstance(segment, dict) or not all(
            isinstance(segment.get(field), str) and segment[field].strip()
            for field in ("id", "text")
        ):
            raise ValueError("Cada tramo necesita id y texto no vacios.")
        identifier = str(segment["id"])
        if not identifier.replace("_", "").replace("-", "").isalnum():
            raise ValueError("El id de tramo solo admite letras, numeros, - y _.")
        result.append(
            {
                "id": identifier,
                "title": str(segment.get("title", identifier)),
                "text": str(segment["text"]).strip(),
            }
        )
    if len({item["id"] for item in result}) != len(result):
        raise ValueError("Los ids de narracion deben ser unicos.")
    return result


def _voices(client: httpx.Client, key: str, *, language: str | None = None) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    next_page: str | None = None
    while True:
        params: dict[str, str | int] = {"page_size": 100}
        if language is not None:
            params["language"] = language
        if next_page is not None:
            params["next_page_token"] = next_page
        response = client.get(
            "https://api.elevenlabs.io/v2/voices",
            headers={"xi-api-key": key},
            params=params,
        )
        if response.status_code != 200:
            raise RuntimeError(f"ElevenLabs voices devolvio HTTP {response.status_code}.")
        payload = response.json()
        voices = payload.get("voices", [])
        if not isinstance(voices, list):
            raise RuntimeError("Respuesta de voces ElevenLabs invalida.")
        found.extend(voice for voice in voices if isinstance(voice, dict))
        if not payload.get("has_more"):
            return found
        next_page = payload.get("next_page_token")
        if not isinstance(next_page, str) or not next_page:
            raise RuntimeError("Paginacion de voces ElevenLabs incompleta.")


def choose_voice(voices: list[dict[str, Any]], *, spanish_filtered: bool = False) -> str:
    if not voices:
        raise RuntimeError("La cuenta de ElevenLabs no tiene voces disponibles.")
    for voice in voices:
        labels = voice.get("labels") or {}
        languages = voice.get("verified_languages") or []
        detail = f"{voice.get('name', '')} {labels} {languages}".casefold()
        codes = {
            str(language.get("language", "")).casefold()
            for language in languages
            if isinstance(language, dict)
        }
        if "es" in codes or any(
            term in detail for term in ("spanish", "español", "es-es", "es-mx", "es-co")
        ):
            return str(voice["voice_id"])
    if spanish_filtered:
        return str(voices[0]["voice_id"])
    raise RuntimeError("No hay voz en espanol identificable en la cuenta; usa --voice-id.")


def probe_duration(path: Path) -> float:
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    duration = float(completed.stdout.strip())
    if duration <= 0:
        raise ValueError("La duracion del clip debe ser positiva.")
    return duration


def generate(
    script: Path = SCRIPT,
    *,
    output: Path = BASE,
    voice_id: str | None = None,
    list_voices: bool = False,
    key_file: Path = KEY_FILE,
    client: httpx.Client | None = None,
) -> list[dict[str, str | float]]:
    key = require_key(key_file)
    owned_client = client is None
    active_client = client or httpx.Client(timeout=60, follow_redirects=False)
    try:
        if list_voices:
            for voice in _voices(active_client, key):
                print(f"{voice.get('name', '')}\t{voice.get('voice_id', '')}")
            return []
        chosen = voice_id or choose_voice(
            _voices(active_client, key, language="es"), spanish_filtered=True
        )
        segments = load_segments(script)
        audio = output / "audio"
        audio.mkdir(parents=True, exist_ok=True)
        clips: list[dict[str, str | float]] = []
        for segment in segments:
            payload = f"{MODEL}\n{chosen}\n{segment['text']}".encode()
            digest = hashlib.sha256(payload).hexdigest()[:20]
            path = audio / f"{segment['id']}-{digest}.mp3"
            if not path.exists():
                response = active_client.post(
                    f"{API_BASE}/text-to-speech/{chosen}",
                    params={"output_format": "mp3_44100_128"},
                    headers={"xi-api-key": key, "Accept": "audio/mpeg"},
                    json={"text": segment["text"], "model_id": MODEL},
                )
                if response.status_code != 200:
                    raise RuntimeError(f"ElevenLabs TTS devolvio HTTP {response.status_code}.")
                if not response.content:
                    raise RuntimeError("ElevenLabs devolvio audio vacio.")
                path.write_bytes(response.content)
            duration = probe_duration(path)
            clips.append(
                {
                    "id": segment["id"],
                    "title": segment["title"],
                    "text": segment["text"],
                    "file": str(path.relative_to(output)).replace("\\", "/"),
                    "duration": round(duration, 3),
                    "voice_id": chosen,
                }
            )
        (output / "narration_durations.json").write_text(
            json.dumps({"model": MODEL, "clips": clips}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return clips
    finally:
        if owned_client:
            active_client.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--script", type=Path, default=SCRIPT)
    parser.add_argument("--output", type=Path, default=BASE)
    parser.add_argument("--voice-id")
    parser.add_argument("--list-voices", action="store_true")
    args = parser.parse_args(argv)
    try:
        clips = generate(
            args.script, output=args.output, voice_id=args.voice_id, list_voices=args.list_voices
        )
    except (
        OSError,
        ValueError,
        RuntimeError,
        httpx.HTTPError,
        subprocess.CalledProcessError,
    ) as exc:
        parser.exit(1, f"Error de narracion: {exc}\n")
    if not args.list_voices:
        for clip in clips:
            print(f"{clip['id']}: {clip['duration']:.3f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
