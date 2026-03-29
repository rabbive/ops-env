"""Compatibility imports for OpenEnv core."""

from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

try:
    from openenv.core.client_types import StepResult
    from openenv.core.env_client import EnvClient
    from openenv.core.env_server.http_server import create_app
    from openenv.core.env_server.interfaces import Environment
    from openenv.core.env_server.types import Action, Observation, State

    OPENENV_AVAILABLE = True
except ImportError:  # pragma: no cover - only used when openenv is unavailable
    OPENENV_AVAILABLE = False

    class Action(BaseModel):
        """Fallback action base class."""

    class Observation(BaseModel):
        """Fallback observation base class."""

        done: bool = False
        reward: float = 0.0
        metadata: dict[str, Any] = Field(default_factory=dict)

    class State(BaseModel):
        """Fallback state base class."""

        episode_id: str
        step_count: int = 0

    ObservationT = TypeVar("ObservationT", bound=Observation)

    class StepResult(BaseModel, Generic[ObservationT]):
        """Fallback step result model."""

        observation: ObservationT
        reward: Optional[float] = None
        done: bool = False
        info: dict[str, Any] = Field(default_factory=dict)

    class Environment:
        """Fallback environment base class."""

    ActionT = TypeVar("ActionT", bound=Action)
    StateT = TypeVar("StateT", bound=State)

    class EnvClient(Generic[ActionT, ObservationT, StateT]):
        """Fallback client that explains why OpenEnv is required."""

        def __init__(self, base_url: Optional[str] = None):
            self.base_url = base_url

        @classmethod
        def from_docker_image(cls, *_args: Any, **_kwargs: Any):
            raise RuntimeError("OpenEnv is required to use the HTTP/WebSocket client.")

        @classmethod
        def from_hub(cls, *_args: Any, **_kwargs: Any):
            raise RuntimeError("OpenEnv is required to use the Hugging Face client.")

        def sync(self):
            return self

        def close(self):
            return None

    def create_app(*_args: Any, **_kwargs: Any):  # pragma: no cover - import shim
        try:
            from fastapi import FastAPI
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "FastAPI and OpenEnv are required to run the server application."
            ) from exc

        app = FastAPI(title="SupportDeskEnv Fallback App")

        @app.get("/health")
        async def health():
            return {"status": "missing-openenv"}

        return app
