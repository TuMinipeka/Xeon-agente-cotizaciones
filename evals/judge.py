"""Scenario judge for semantic qualities only; deterministic checks own hard facts."""

from __future__ import annotations

import time
from contextvars import ContextVar
from typing import Any

JUDGE_TIMEOUT_RETRY: ContextVar[bool] = ContextVar("judge_timeout_retry", default=False)


def build_judge(criteria: list[str], *, model: str, api_base: str, api_key: str) -> Any:
    from litellm.exceptions import Timeout
    from scenario import JudgeAgent

    class RetryingJudgeAgent(JudgeAgent):  # type: ignore[misc]
        def _completion(self, **kwargs: Any) -> Any:
            # The network guard counts every LiteLLM completion. Suppress its
            # transport timeout retry here so the judge gets exactly one retry.
            token = JUDGE_TIMEOUT_RETRY.set(True)
            try:
                for attempt in range(2):
                    try:
                        return super()._completion(**kwargs)
                    except Timeout:
                        if attempt:
                            raise
                        time.sleep(0.2)
                raise AssertionError("Unreachable judge retry state")
            finally:
                JUDGE_TIMEOUT_RETRY.reset(token)

    judge = RetryingJudgeAgent(
        criteria=criteria,
        model=model,
        api_base=api_base,
        api_key=api_key,
        max_tokens=256,
        num_retries=0,
        timeout=120,
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
