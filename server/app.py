"""FastAPI app entrypoint for supportdesk_env."""

from __future__ import annotations

try:
    from openenv.core.env_server.http_server import create_app
except ImportError:  # pragma: no cover - source-tree fallback
    try:
        from ..compat import create_app
    except ImportError:
        from compat import create_app

try:
    from ..models import SupportDeskAction, SupportDeskObservation
    from .supportdesk_environment import SupportDeskEnvironment
except ImportError:  # pragma: no cover - source-tree fallback
    from models import SupportDeskAction, SupportDeskObservation
    from server.supportdesk_environment import SupportDeskEnvironment

app = create_app(
    SupportDeskEnvironment,
    SupportDeskAction,
    SupportDeskObservation,
    env_name="supportdesk_env",
)


def main() -> None:
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        ws_ping_interval=300,
        ws_ping_timeout=300,
    )


if __name__ == "__main__":
    main()
