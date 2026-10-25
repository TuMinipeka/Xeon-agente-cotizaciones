from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from scripts.video import edit, narrate, record


def test_gdigrab_command_and_worker_close_ffmpeg_with_q(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    command = record.recording_command(tmp_path / "escena1.mp4")
    assert command[:4] == ["ffmpeg", "-hide_banner", "-loglevel", "warning"]
    assert command[command.index("-f") + 1] == "gdigrab"
    assert command[command.index("-framerate") + 1] == "30"
    assert command[command.index("-i") + 1] == "desktop"
    assert command[command.index("-preset") + 1] == "veryfast"
    assert command[command.index("-crf") + 1] == "20"
    assert "-an" in command

    class FakeProcess:
        pid = 4321
        stdin = io.BytesIO()

        def poll(self) -> None:
            return None

        def wait(self) -> int:
            return 0

    process = FakeProcess()
    monkeypatch.setattr(record.subprocess, "Popen", lambda *_args, **_kwargs: process)

    def request_stop(_seconds: float) -> None:
        (tmp_path / record.STOP_REQUEST.name).write_text("q", encoding="ascii")

    monkeypatch.setattr(record.time, "sleep", request_stop)
    assert record.worker("escena1", raw=tmp_path) == 0
    assert process.stdin.getvalue() == b"q\n"
    assert not (tmp_path / record.STATE.name).exists()


def test_record_start_and_stop_use_state_without_ffmpeg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeSupervisor:
        def poll(self) -> None:
            return None

    def spawn(*_args: object, **_kwargs: object) -> FakeSupervisor:
        (tmp_path / record.STATE.name).write_text(
            json.dumps({"name": "escena2", "supervisor_pid": 1, "ffmpeg_pid": 2}),
            encoding="utf-8",
        )
        return FakeSupervisor()

    monkeypatch.setattr(record.subprocess, "Popen", spawn)
    output = record.start("escena2", raw=tmp_path)
    assert output == tmp_path / "escena2.mp4"
    with pytest.raises(RuntimeError, match="grabacion activa"):
        record.start("escena3", raw=tmp_path)
    output.write_bytes(b"mock mp4")

    def close_after_request(_seconds: float) -> None:
        assert (tmp_path / record.STOP_REQUEST.name).read_text(encoding="ascii") == "q\n"
        (tmp_path / record.STATE.name).unlink()

    monkeypatch.setattr(record.time, "sleep", close_after_request)
    assert record.stop(raw=tmp_path) == output
    with pytest.raises(ValueError, match="nombre de escena"):
        record.start("../otro", raw=tmp_path)


def test_narration_requires_local_key_without_exposing_it(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match=r"Falta secrets/elevenlabs_api_key\.txt"):
        narrate.require_key(tmp_path / "absent")


def test_default_voice_prefers_verified_spanish_from_account() -> None:
    voices = [
        {"voice_id": "english", "name": "English", "verified_languages": []},
        {"voice_id": "spanish", "name": "Voz local", "verified_languages": [{"language": "es"}]},
    ]
    assert narrate.choose_voice(voices) == "spanish"
    with pytest.raises(RuntimeError, match="usa --voice-id"):
        narrate.choose_voice(voices[:1])


def test_ffprobe_duration_and_text_script_without_real_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []

    class Result:
        stdout = "4.125\n"

    def fake_run(command: list[str], **_kwargs: object) -> Result:
        calls.append(command)
        return Result()

    monkeypatch.setattr(narrate.subprocess, "run", fake_run)
    assert narrate.probe_duration(tmp_path / "clip.mp3") == 4.125
    assert calls[0][0] == "ffprobe"
    assert "format=duration" in calls[0]
    script = tmp_path / "voz.txt"
    script.write_text("Un tramo de narracion.", encoding="utf-8")
    assert narrate.load_segments(script) == [
        {"id": "voz", "title": "voz", "text": "Un tramo de narracion."}
    ]


def test_narration_uses_mock_http_cache_and_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    secret = "test-secret-value"
    key_file = tmp_path / "key.txt"
    key_file.write_text(secret, encoding="utf-8")
    script = tmp_path / "script.json"
    script.write_text(
        json.dumps({"segments": [{"id": "escena1", "title": "Uno", "text": "Hola XEON"}]}),
        encoding="utf-8",
    )
    calls: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        assert request.headers["xi-api-key"] == secret
        if request.url.path.endswith("/voices"):
            if len(calls) <= 1 or len(calls) == 3:
                assert request.url.params["language"] == "es"
            return httpx.Response(
                200,
                json={
                    "voices": [
                        {
                            "voice_id": "es-voice",
                            "name": "Voz española",
                            "labels": {"language": "Spanish"},
                        }
                    ]
                },
            )
        assert request.url.path.endswith("/text-to-speech/es-voice")
        assert request.read().decode("utf-8").find("eleven_multilingual_v2") >= 0
        return httpx.Response(200, content=b"fake mp3")

    monkeypatch.setattr(narrate, "probe_duration", lambda _path: 3.25)
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        first = narrate.generate(script, output=tmp_path / "out", key_file=key_file, client=client)
        second = narrate.generate(script, output=tmp_path / "out", key_file=key_file, client=client)
        voices = narrate.generate(
            script, output=tmp_path / "out", key_file=key_file, client=client, list_voices=True
        )
    assert len(first) == 1 and first == second
    assert first[0]["duration"] == 3.25
    assert voices == []
    assert calls.count("/v1/text-to-speech/es-voice") == 1
    assert calls.count("/v2/voices") == 3
    printed = capsys.readouterr().out
    assert "Voz española\tes-voice" in printed
    assert secret not in printed
    assert secret not in (tmp_path / "out" / "narration_durations.json").read_text(encoding="utf-8")


def test_voice_listing_paginates_without_network() -> None:
    seen: list[str | None] = []

    def respond(request: httpx.Request) -> httpx.Response:
        token = request.url.params.get("next_page_token")
        seen.append(token)
        return httpx.Response(
            200,
            json={
                "voices": [{"voice_id": "v1" if token is None else "v2"}],
                "has_more": token is None,
                "next_page_token": "page-2" if token is None else None,
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        assert [voice["voice_id"] for voice in narrate._voices(client, "fake")] == ["v1", "v2"]
    assert seen == [None, "page-2"]


def _edit_fixture(base: Path) -> None:
    base.mkdir(parents=True)
    segments = []
    clips = []
    for identifier in edit.SCENES:
        segments.append(
            {
                "id": identifier,
                "title": identifier,
                "text": f"Narracion {identifier}",
                "labels": [identifier],
            }
        )
        clips.append({"id": identifier, "file": f"audio/{identifier}.mp3", "duration": 2.0})
    marks: list[dict[str, Any]] = [
        {
            "id": identifier,
            "file": f"{identifier}.mp4",
            "start": 0,
            "end": 20,
            "speedups": [{"start": 8, "end": 16, "factor": 8}],
        }
        for identifier in edit.SCENES[1:-1]
    ]
    (base / "narration.json").write_text(json.dumps({"segments": segments}), encoding="utf-8")
    (base / "narration_durations.json").write_text(json.dumps({"clips": clips}), encoding="utf-8")
    (base / "marks.json").write_text(json.dumps({"scenes": marks}), encoding="utf-8")


def test_edit_plan_builds_speedups_titles_subtitles_and_dry_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = tmp_path / "video" / "hito2"
    _edit_fixture(base)
    plan = edit.build_plan(base)
    assert plan.output.name == "XEON_HITO2_demo.mp4"
    assert plan.srt.name == "XEON_HITO2_demo.srt"
    assert len(plan.commands) == 16  # 2 titles + 12 scene parts + concat + mix
    assert sum("(PTS-STARTPTS)/8" in " ".join(cmd) for cmd in plan.commands) == 4
    assert sum("espera acortada" in " ".join(cmd) for cmd in plan.commands) == 4
    assert "00:00:00,250 --> 00:00:02,250" in plan.subtitle
    assert "00:00:10,250" in plan.subtitle
    assert "Narracion cierre" in plan.subtitle
    assert "amix=inputs=6" in " ".join(plan.commands[-1])
    assert "subtitles=" in " ".join(plan.commands[-1])
    assert "-c:v libx264" in " ".join(plan.commands[-1])
    edit.execute(plan, dry_run=True)
    assert capsys.readouterr().out.count("ffmpeg") == len(plan.commands)
    assert not plan.output.exists()
    assert not plan.srt.exists()


def test_edit_rejects_unfilled_marks(tmp_path: Path) -> None:
    base = tmp_path / "video" / "hito2"
    _edit_fixture(base)
    marks_path = base / "marks.json"
    marks = json.loads(marks_path.read_text(encoding="utf-8"))
    marks["scenes"][0]["end"] = None
    marks_path.write_text(json.dumps(marks), encoding="utf-8")
    with pytest.raises(ValueError, match="Completa inicio y fin"):
        edit.build_plan(base)


def test_edit_execute_writes_srt_and_runs_commands_without_real_ffmpeg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = tmp_path / "video" / "hito2"
    _edit_fixture(base)
    plan = edit.build_plan(base)
    calls: list[tuple[tuple[str, ...], Path]] = []

    def fake_run(command: tuple[str, ...], *, cwd: Path, check: bool) -> None:
        assert check is True
        calls.append((command, cwd))

    monkeypatch.setattr(edit.subprocess, "run", fake_run)
    edit.execute(plan)
    assert len(calls) == len(plan.commands)
    assert all(cwd == tmp_path for _, cwd in calls)
    assert plan.srt.read_text(encoding="utf-8") == plan.subtitle
    assert (plan.work / "concat.txt").read_text(encoding="utf-8") == plan.concat_list
