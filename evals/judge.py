"""Scenario judge for semantic qualities only; deterministic checks own hard facts."""

from __future__ import annotations

from typing import Any


def build_judge(criteria: list[str], *, model: str, api_base: str, api_key: str) -> Any:
    from scenario import JudgeAgent

    judge = JudgeAgent(
        criteria=criteria,
        model=model,
        api_base=api_base,
        api_key=api_key,
        max_tokens=256,
        num_retries=0,
        timeout=30,
    )
    judge._provider_compat._adaptations.add("drop_temperature")
    return judge


def semantic_verdict(success: bool, reasoning: str, *, confidence: float | None) -> dict[str, str]:
    if success:
        status = "PASS"
    elif confidence is None or confidence < 0.7:
        status = "HINT"
    else:
        status = "FAIL"
    return {"status": status, "reasoning": reasoning, "scope": "clarity_relevance_tone_ambiguity"}
