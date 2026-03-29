## Learned User Preferences

- When discussing submission or roadmap, distinguish what the repository automates (tests, `openenv validate`, scripted baselines) from steps that depend on the local machine or external services (Docker engine, Hugging Face login and Space configuration, organizer-provided pre-submission scripts).

## Learned Workspace Facts

- This workspace is an OpenEnv **support desk triage** environment (`supportdesk_env`): graded customer-support workflows with typed Pydantic models, FastAPI app in `server/app.py`, core logic in `server/supportdesk_environment.py` and `server/grader.py`, manifest `openenv.yaml`, and root `inference.py` plus optional `inference.py --scripted` gold trajectories.
- Drive the HTTP/WebSocket client synchronously with `SupportDeskEnv(...).sync()` when scripts call `reset`/`step` in a blocking style; the underlying OpenEnv `EnvClient` is async-first.
- Local pre-submission checks are bundled in `scripts/validate_submission.sh` (typically `uv sync`, `pytest`, `openenv validate`, scripted inference, and `docker build` when Docker is installed).
- The Cursor MCP folder named `user-MCP_DOCKER` in this project exposes session/browser-oriented tools, not a substitute for the host `docker` CLI when building or running images.
