"""Baseline inference script for supportdesk_env.

STDOUT FORMAT (mandatory for evaluation):

    [START] task=<task_name> env=supportdesk_env model=<model_name>
    [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
    [END]   success=<true|false> steps=<n> score=<0.00> rewards=<r1,r2,...,rn>

Human-readable progress goes to stderr unless INFERENCE_VERBOSE=0.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import textwrap
from typing import Any, Optional

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
HF_TOKEN = os.getenv("HF_TOKEN")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
ENV_BASE_URL = os.getenv("ENV_BASE_URL")
LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")
MAX_STEPS = int(os.getenv("MAX_STEPS", "20"))
TEMPERATURE = 0
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "350"))
VERBOSE = os.getenv("INFERENCE_VERBOSE", "1") != "0"
BENCHMARK = "supportdesk_env"

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
      "operation": "<one of the operations below>",
      "task_id": "string (for select_task)",
      "query": "string (for search_docs)",
      "resource_id": "string (for open_resource)",
      "priority": "low|normal|high|urgent (for set_priority)",
      "queue": "account_access|billing|account_security|general_support (for set_queue)",
      "tags": ["tag1","tag2"] (for set_tags),
      "resolution_code": "send_reset_link|explain_authorization_hold|security_escalation|request_more_info (for set_resolution_code)",
      "text": "string (for save_internal_note or save_reply)"
    }

    Workflow — follow this order, do NOT repeat steps you already completed:
    1. search_docs — search once or twice to find relevant resources
    2. open_resource — open each resource found in search results by its resource_id
    3. set_queue — set the correct queue based on the ticket and docs
    4. set_priority — set appropriate priority
    5. set_tags — set relevant tags
    6. set_resolution_code — set the resolution code
    7. save_internal_note — write an internal note summarizing findings
    8. save_reply — write a professional, policy-safe customer reply
    9. submit — finalize the ticket

    Rules:
    - Emit exactly one action per turn.
    - NEVER repeat the same operation with the same arguments. If search returned results, open them; do not search again.
    - After searching, always open_resource on the resource_ids from search results before setting fields.
    - Base queue, priority, tags, and resolution_code on evidence from opened documents.
    - Keep customer replies concise and policy-safe. Never ask for passwords or credentials.
    """
).strip()


# ---------------------------------------------------------------------------
# Structured stdout logging (matches organizer format exactly)
# ---------------------------------------------------------------------------

def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    done_val = str(done).lower()
    error_val = error if error else "null"
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: list[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} score={score:.2f} rewards={rewards_str}",
        flush=True,
    )


def _log_human(msg: str) -> None:
    if VERBOSE:
        print(msg, file=sys.stderr)


# ---------------------------------------------------------------------------
# Action formatting
# ---------------------------------------------------------------------------

def _action_str(action: SupportDeskAction) -> str:
    """Format action as a readable call string, e.g. search_docs('password reset')."""
    op = action.operation
    if op == "select_task":
        return f"select_task('{action.task_id}')"
    elif op == "search_docs":
        return f"search_docs('{action.query}')"
    elif op == "open_resource":
        return f"open_resource('{action.resource_id}')"
    elif op == "set_queue":
        return f"set_queue('{action.queue}')"
    elif op == "set_priority":
        return f"set_priority('{action.priority}')"
    elif op == "set_tags":
        tags = ",".join(f"'{t}'" for t in (action.tags or []))
        return f"set_tags([{tags}])"
    elif op == "set_resolution_code":
        return f"set_resolution_code('{action.resolution_code}')"
    elif op == "save_internal_note":
        text = (action.text or "")[:60]
        return f"save_internal_note('{text}...')"
    elif op == "save_reply":
        text = (action.text or "")[:60]
        return f"save_reply('{text}...')"
    elif op == "submit":
        return "submit()"
    return f"{op}()"


def _action_json(action: SupportDeskAction) -> dict[str, Any]:
    return action.model_dump(mode="json", exclude_none=True)


def _get_error(observation: Any) -> Optional[str]:
    """Extract the last error from recent_feedback, if any."""
    for fb in reversed(observation.recent_feedback or []):
        lower = fb.lower()
        if "error" in lower or "invalid" in lower or "already" in lower or "penalty" in lower:
            return fb.replace("\n", " ")
    return None


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Task runner
# ---------------------------------------------------------------------------

def run_task(env: Any, client: OpenAI, task_id: str) -> float:
    env.reset()
    select_action = SupportDeskAction(operation="select_task", task_id=task_id)
    result = env.step(select_action)
    observation = result.observation

    log_start(task=task_id, env=BENCHMARK, model=MODEL_NAME)

    rewards: list[float] = [float(result.reward)]
    log_step(
        step=0,
        action=_action_str(select_action),
        reward=float(result.reward),
        done=bool(result.done),
        error=_get_error(observation),
    )
    _log_human(f"\n=== {task_id} ===\nTask: {observation.task_title}")

    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    recent_action_sigs: list[str] = []
    steps_taken = 0

    for step in range(1, MAX_STEPS + 1):
        if result.done:
            break

        prompt = build_prompt(observation)
        if recent_action_sigs:
            history_block = "\n".join(f"- {a}" for a in recent_action_sigs[-6:])
            prompt += f"\n\nYour previous actions this episode (do NOT repeat):\n{history_block}"

        messages.append({"role": "user", "content": prompt})
        if len(messages) > 12:
            messages = [messages[0]] + messages[-11:]

        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )
        response_text = completion.choices[0].message.content or ""
        messages.append({"role": "assistant", "content": response_text})
        action = parse_action(response_text)

        action_sig = json.dumps(_action_json(action), sort_keys=True)
        repeat_count = sum(1 for a in recent_action_sigs if a == action_sig)
        if repeat_count >= 2:
            _log_human(f"Step {step}: loop detected, forcing submit")
            action = SupportDeskAction(operation="submit")
            action_sig = json.dumps(_action_json(action), sort_keys=True)
        recent_action_sigs.append(action_sig)

        _log_human(f"Step {step}: {action.model_dump(exclude_none=True)}")
        result = env.step(action)
        observation = result.observation
        reward = float(result.reward)
        rewards.append(reward)
        steps_taken = step

        log_step(
            step=step,
            action=_action_str(action),
            reward=reward,
            done=bool(result.done),
            error=_get_error(observation),
        )
        _log_human(
            f"  reward={result.reward:.3f} done={result.done} score={observation.score:.3f}"
        )
        if result.done:
            break

    final_score = min(max(float(observation.score), 0.0), 1.0)
    success = final_score > 0.0 and result.done

    log_end(
        success=success,
        steps=steps_taken,
        score=final_score,
        rewards=rewards,
    )
    _log_human(f"Final score: {final_score:.3f}")
    return final_score


# ---------------------------------------------------------------------------
# Scripted baseline runner (emits same structured logs)
# ---------------------------------------------------------------------------

def run_scripted() -> None:
    if run_all_scripted is None:
        print("scripted_baselines module not found.", file=sys.stderr)
        sys.exit(1)

    scores = run_all_scripted()
    for task_id, score in scores.items():
        log_start(task=task_id, env=BENCHMARK, model="scripted")
        log_step(step=1, action="scripted_gold_trajectory()", reward=float(score), done=True, error=None)
        log_end(
            success=score >= 0.5,
            steps=1,
            score=float(score),
            rewards=[float(score)],
        )

    _log_human("=== Scripted baseline (deterministic gold trajectories, no LLM) ===")
    for task_id, score in scores.items():
        _log_human(f"{task_id}: {score:.3f}")
    average = sum(scores.values()) / len(scores)
    _log_human(f"average: {average:.3f}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

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
        run_scripted()
        return

    if not MODEL_NAME:
        raise RuntimeError("MODEL_NAME must be set.")
    if not HF_TOKEN:
        raise RuntimeError("HF_TOKEN must be set.")

    client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)

    if ENV_BASE_URL:
        raw_env = SupportDeskEnv(base_url=ENV_BASE_URL)
    else:
        if not LOCAL_IMAGE_NAME:
            raise RuntimeError(
                "LOCAL_IMAGE_NAME must be set when ENV_BASE_URL is not set."
            )
        raw_env = asyncio.run(SupportDeskEnv.from_docker_image(LOCAL_IMAGE_NAME))

    env = raw_env.sync()
    scores: dict[str, float] = {}
    try:
        for task_id in TASK_ORDER:
            scores[task_id] = run_task(env, client, task_id)
    finally:
        env.close()

    _log_human("\n=== Summary ===")
    for task_id, score in scores.items():
        _log_human(f"{task_id}: {score:.3f}")
    average = sum(scores.values()) / len(scores)
    _log_human(f"average: {average:.3f}")


if __name__ == "__main__":
    main()
