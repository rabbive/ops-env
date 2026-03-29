"""Typed OpenEnv client for the support desk environment."""

from __future__ import annotations

from typing import Any

try:
    from .compat import EnvClient, State, StepResult
    from .models import SupportDeskAction, SupportDeskObservation, SupportDeskState
except ImportError:  # pragma: no cover - source-tree fallback
    from compat import EnvClient, State, StepResult
    from models import SupportDeskAction, SupportDeskObservation, SupportDeskState


class SupportDeskEnv(EnvClient[SupportDeskAction, SupportDeskObservation, SupportDeskState]):
    """WebSocket client for a running SupportDesk OpenEnv server."""

    def _step_payload(self, action: SupportDeskAction) -> dict[str, Any]:
        return action.model_dump(exclude_none=True)

    def _parse_result(self, payload: dict[str, Any]) -> StepResult[SupportDeskObservation]:
        observation_payload = payload.get("observation", payload)
        obs_data = dict(observation_payload)
        if "reward" not in obs_data and "reward" in payload:
            obs_data["reward"] = payload.get("reward")
        if "done" not in obs_data and "done" in payload:
            obs_data["done"] = payload.get("done")
        observation = SupportDeskObservation.model_validate(obs_data)
        return StepResult(
            observation=observation,
            reward=payload.get("reward", observation.reward),
            done=payload.get("done", observation.done),
        )

    def _parse_state(self, payload: dict[str, Any]) -> State:
        return SupportDeskState.model_validate(payload)
