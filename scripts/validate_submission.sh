#!/usr/bin/env bash
# Pre-submission checks: tests, openenv validate, scripted baseline, optional docker build.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> uv sync (dev)"
uv sync --extra dev

echo "==> pytest"
uv run pytest

echo "==> openenv validate"
uv run openenv validate --verbose

echo "==> scripted inference baseline"
uv run python inference.py --scripted

if command -v docker >/dev/null 2>&1; then
  echo "==> docker build"
  docker build -t supportdesk-env:latest .
  echo "Docker OK. Run: docker run --rm -p 8000:8000 supportdesk-env:latest"
else
  echo "==> docker not found; skipping docker build (install Docker to include this step)."
fi

echo "==> All local checks passed."
