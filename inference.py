"""Baseline inference script for supportdesk_env.

Structured evaluation logs (stdout, one JSON object per line; parseable by automated evaluators):

  [START] {\"phase\":\"run\"|\"scripted\", ...}
  [STEP]  {\"step\":int,\"task_id\":str,\"action\":{...},\"reward\":float,\"score\":float,\"done\":bool}
  [END]   {\"phase\":\"run\"|\"scripted\",\"scores\":{...},\"average\":float}

Human-readable progress goes to stderr unless INFERENCE_VERBOSE=0.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import textwrap
from typing import Any

from openai import OpenAI

try:
    from supportdesk_env import SupportDeskAction, SupportDeskEnv
except ImportError:  # pragma: no cover - source-tree fallback
    from client import SupportDeskEnv
    from models import SupportDeskAction

try:
    from scripted_baselines import run_all_scripted
except ImportError:  # pragma: no cover - source-tree fallback
    run_all_scripted = None  # type: ignore[misc, assignment]

API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
API_KEY = os.getenv("HF_TOKEN") or os.getenv("OPENAI_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME")
ENV_BASE_URL = os.getenv("ENV_BASE_URL")
# Hard tasks need 13+ environment steps (search, opens, draft, submit); keep headroom.
MAX_STEPS = int(os.getenv("MAX_STEPS", "20"))
TEMPERATURE = 0
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "350"))
IMAGE_NAME = os.getenv("ENV_IMAGE_NAME", "supportdesk-env:latest")
VERBOSE = os.getenv("INFERENCE_VERBOSE", "1") != "0"

TASK_ORDER = [
    "task_easy_password_reset",
    "task_medium_duplicate_charge",
    "task_hard_security_incident",
]

SYSTEM_PROMPT = textwrap.dedent(
    """
    You are operating a deterministic support desk environment.
    Reply with exactly one JSON object and no surrounding commentary.

    Valid schema:
    {
      "operation": "select_task|search_docs|open_resource|set_priority|set_queue|set_tags|set_resolution_code|save_internal_note|save_reply|submit",
      "task_id": "optional string",
      "query": "optional string",
      "resource_id": "optional string",
      "priority": "optional string",
      "queue": "optional string",
      "tags": ["optional", "tags"],
      "resolution_code": "optional string",
      "text": "optional string"
    }

    Rules:
    - Only emit one action.
    - Prefer investigating internal docs before submitting.
    - Keep replies concise and policy-safe.
    """
).strip()


def _structured_log(tag: str, payload: dict[str, Any]) -> None:
    """Emit one evaluation line: [TAG] <compact JSON>. Keys sorted for stable ordering."""
    line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    print(f"[{tag}] {line}")


def _log_human(msg: str) -> None:
    if VERBOSE:
        print(msg, file=sys.stderr)


def _action_json(action: SupportDeskAction) -> dict[str, Any]:
    return action.model_dump(mode="json", exclude_none=True)


def build_prompt(observation: Any) -> str:
    task_lines = []
    for task in observation.available_tasks:
        task_lines.append(
            f"- {task.task_id}: {task.title} ({task.difficulty}) :: {task.customer_summary}"
        )
    resource_lines = []
    for resource in observation.resource_catalog:
        opened = "opened" if resource.opened else "closed"
        resource_lines.append(
            f"- {resource.resource_id} [{resource.kind}, {opened}] {resource.title}: {resource.summary}"
        )
    search_lines = []
    for result in observation.search_results[:4]:
        search_lines.append(
            f"- {result.resource_id}: {result.title} :: {result.snippet}"
        )
    opened_resource = ""
    if observation.open_resource is not None:
        opened_resource = textwrap.dedent(
            f"""
            Most recently opened resource:
            - id: {observation.open_resource.resource_id}
            - title: {observation.open_resource.title}
            - content: {observation.open_resource.content}
            - key facts: {", ".join(observation.open_resource.key_facts)}
            """
        ).strip()
    draft = observation.current_draft
    return textwrap.dedent(
        f"""
        Phase: {observation.phase}
        Instructions:
        {observation.instructions}

        Available tasks:
        {chr(10).join(task_lines) if task_lines else "(none)"}

        Active task: {observation.task_id or "(none)"} / {observation.task_title or "(none)"}
        Current draft:
        - queue: {draft.queue or "(unset)"}
        - priority: {draft.priority or "(unset)"}
        - tags: {draft.tags or []}
        - resolution_code: {draft.resolution_code or "(unset)"}
        - internal_note: {draft.internal_note or "(empty)"}
        - reply: {draft.reply or "(empty)"}

        Resource catalog:
        {chr(10).join(resource_lines) if resource_lines else "(none)"}

        Search results:
        {chr(10).join(search_lines) if search_lines else "(none)"}

        {opened_resource or "Most recently opened resource: (none)"}

        Recent feedback:
        {chr(10).join(f"- {item}" for item in observation.recent_feedback) if observation.recent_feedback else "(none)"}

        Current score: {observation.score:.2f}
        Steps remaining: {observation.steps_remaining}
        """
    ).strip()


def parse_action(response_text: str) -> SupportDeskAction:
    match = re.search(r"\{.*\}", response_text, re.DOTALL)
    if not match:
        raise ValueError(f"Model did not return JSON: {response_text}")
    data = json.loads(match.group(0))
    return SupportDeskAction.model_validate(data)


def run_task(env: Any, client: OpenAI, task_id: str) -> float:
    env.reset()
    select_action = SupportDeskAction(operation="select_task", task_id=task_id)
    result = env.step(select_action)
    observation = result.observation
    _structured_log(
        "STEP",
        {
            "action": _action_json(select_action),
            "done": bool(result.done),
            "reward": float(result.reward),
            "score": float(observation.score),
            "step": 0,
            "task_id": task_id,
        },
    )
    _log_human(f"\n=== {task_id} ===\nTask: {observation.task_title}")

    for step in range(1, MAX_STEPS + 1):
        if result.done:
            break
        prompt = build_prompt(observation)
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )
        response_text = completion.choices[0].message.content or ""
        action = parse_action(response_text)
        _log_human(f"Step {step}: {action.model_dump(exclude_none=True)}")
        result = env.step(action)
        observation = result.observation
        _structured_log(
            "STEP",
            {
                "action": _action_json(action),
                "done": bool(result.done),
                "reward": float(result.reward),
                "score": float(observation.score),
                "step": step,
                "task_id": task_id,
            },
        )
        _log_human(
            f"  reward={result.reward:.3f} done={result.done} score={observation.score:.3f}"
        )
        if result.done:
            break

    final_score = float(observation.score)
    _log_human(f"Final score: {final_score:.3f}")
    return final_score


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM or scripted baseline for supportdesk_env.")
    parser.add_argument(
        "--scripted",
        action="store_true",
        help=(
            "Replay deterministic gold trajectories in-process (no LLM). "
            "Reproducible scores for CI and grader smoke tests."
        ),
    )
    args = parser.parse_args()

    if args.scripted:
        if run_all_scripted is None:
            print("scripted_baselines module not found.", file=sys.stderr)
            sys.exit(1)
        _structured_log(
            "START",
            {
                "phase": "scripted",
                "tasks": list(TASK_ORDER),
            },
        )
        scores = run_all_scripted()
        for task_id, score in scores.items():
            _structured_log(
                "STEP",
                {
                    "score": float(score),
                    "scripted": True,
                    "task_id": task_id,
                },
            )
        average = sum(scores.values()) / len(scores)
        _structured_log(
            "END",
            {
                "average": round(average, 6),
                "phase": "scripted",
                "scores": {k: float(v) for k, v in scores.items()},
            },
        )
        _log_human("=== Scripted baseline (deterministic gold trajectories, no LLM) ===")
        for task_id, score in scores.items():
            _log_human(f"{task_id}: {score:.3f}")
        _log_human(f"average: {average:.3f}")
        return

    if not MODEL_NAME:
        raise RuntimeError("MODEL_NAME must be set.")
    if not API_KEY:
        raise RuntimeError("HF_TOKEN or OPENAI_API_KEY must be set.")

    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

    if ENV_BASE_URL:
        raw_env = SupportDeskEnv(base_url=ENV_BASE_URL)
        env_desc: dict[str, Any] = {"env_base_url": ENV_BASE_URL, "kind": "http"}
    else:
        raw_env = SupportDeskEnv.from_docker_image(IMAGE_NAME)
        env_desc = {"docker_image": IMAGE_NAME, "kind": "docker"}

    _structured_log(
        "START",
        {
            "api_base_url": API_BASE_URL,
            "max_steps": MAX_STEPS,
            "model_name": MODEL_NAME,
            "phase": "run",
            "tasks": list(TASK_ORDER),
            **env_desc,
        },
    )

    env = raw_env.sync()
    scores: dict[str, float] = {}
    try:
        for task_id in TASK_ORDER:
            scores[task_id] = run_task(env, client, task_id)
    finally:
        env.close()

    average = sum(scores.values()) / len(scores)
    _structured_log(
        "END",
        {
            "average": round(average, 6),
            "phase": "run",
            "scores": {k: float(v) for k, v in scores.items()},
        },
    )
    _log_human("\n=== Summary ===")
    for task_id, score in scores.items():
        _log_human(f"{task_id}: {score:.3f}")
    _log_human(f"average: {average:.3f}")


if __name__ == "__main__":
    main()
