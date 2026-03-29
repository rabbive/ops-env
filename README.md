---
title: Support Desk Environment
emoji: 📨
colorFrom: blue
colorTo: teal
sdk: docker
pinned: false
app_port: 8000
base_path: /web
tags:
- openenv
---

# Support Desk Environment

`supportdesk_env` is a deterministic OpenEnv environment for B2B SaaS support operations. An agent must inspect a customer ticket, search internal documentation, route the case correctly, draft an internal note, draft a customer reply, and submit a final resolution through the standard `reset()` / `step()` / `state()` interface.

This is meant to feel like real support work rather than a toy benchmark. The three tasks model common operational patterns:

- Easy: password-reset triage with account-access routing
- Medium: billing dispute analysis for an upgrade-related authorization hold
- Hard: enterprise security escalation with billing anomaly handling

## Why This Environment Is Useful

Support triage is a genuine human workflow with clear objectives, partial progress, and multiple failure modes. Good agents need to:

- gather evidence instead of guessing
- set operational metadata correctly
- communicate clearly to the customer
- avoid unsafe promises and policy violations

That makes it a strong fit for both evaluation and reinforcement learning.

## Action Space

The environment uses one typed Pydantic action model: `SupportDeskAction`.

- `select_task(task_id)`
- `search_docs(query)`
- `open_resource(resource_id)`
- `set_priority(priority)`
- `set_queue(queue)`
- `set_tags(tags)`
- `set_resolution_code(resolution_code)`
- `save_internal_note(text)`
- `save_reply(text)`
- `submit()`

Enumerated values:

- Priorities: `low`, `normal`, `high`, `urgent`
- Queues: `account_access`, `billing`, `account_security`, `general_support`
- Resolution codes: `send_reset_link`, `explain_authorization_hold`, `security_escalation`, `request_more_info`

## Observation Space

`SupportDeskObservation` includes:

- `phase`: `task_selection`, `task_workbench`, or `completed`
- `instructions`: current ticket and workflow guidance
- `available_tasks`: visible task cards on reset
- `task_id` and `task_title`
- `resource_catalog`: internal docs and account records available for review
- `open_resource`: full text of the most recently opened resource
- `search_results`: results from the most recent `search_docs` action
- `current_draft`: queue, priority, tags, resolution code, internal note, reply
- `recent_feedback`: environment hints about progress or invalid behavior
- `steps_remaining`
- `score`: current shaped score estimate
- `reward_breakdown`

`state()` returns the public `SupportDeskState`, which tracks the current task, opened resources, search history, draft content, action history, and last score.

## Tasks

### 1. Expired Password Reset Link (Easy)

The user cannot log in because the reset email expired. The correct solution is to route the ticket to `account_access`, keep priority at `normal`, use tags `password_reset` and `login_issue`, set resolution `send_reset_link`, and tell the customer to use a fresh link within 30 minutes while ignoring older reset emails.

### 2. Duplicate Charge After Plan Upgrade (Medium)

The customer thinks they were double charged after upgrading. The environment expects routing to `billing`, priority `high`, tags `duplicate_charge` and `plan_upgrade`, resolution `explain_authorization_hold`, an internal note that cites both invoice IDs, and a reply that distinguishes an authorization hold from a settled charge without promising an immediate refund.

### 3. Enterprise Security Incident With Billing Anomaly (Hard)

An enterprise admin reports unexpected token activity, a seat spike, and billing concerns. The right outcome is queue `account_security`, priority `urgent`, tags `security_incident`, `billing_anomaly`, and `enterprise_sla`, resolution `security_escalation`, and a reply that covers token revocation, security escalation, a billing review freeze, and the one-hour enterprise SLA while avoiding unsafe requests for passwords or premature refund promises.

## Reward Function

The environment computes a deterministic partial score in `[0.0, 1.0]` from:

- evidence gathering from discovered and opened resources
- queue accuracy
- priority accuracy
- tag quality
- resolution code accuracy
- internal note coverage
- reply coverage
- explicit submission completeness

Each step reward is:

```text
reward = current_partial_score - previous_partial_score - action_penalty
```

Penalties apply to invalid actions, repeated no-progress actions, empty saves, and premature submission. This gives dense trajectory feedback instead of a single sparse reward at episode end.

## Layout

```text
.
├── __init__.py
├── client.py
├── compat.py
├── Dockerfile
├── inference.py
├── models.py
├── openenv.yaml
├── pyproject.toml
├── README.md
├── server/
│   ├── app.py
│   ├── grader.py
│   ├── supportdesk_environment.py
│   └── task_data.py
└── tests/
    ├── test_environment.py
    └── test_grader.py
```

## Setup

### Local Python Setup

```bash
uv sync
```

### Run Tests

```bash
uv run pytest
```

### Validate the OpenEnv Package

```bash
uv run openenv validate --verbose
```

If you want the OpenEnv CLI to build the same default image tag used by `inference.py`, run:

```bash
uv run openenv build -t supportdesk-env:latest
```

### Build and Run With Docker

```bash
docker build -t supportdesk-env:latest .
docker run --rm -p 8000:8000 supportdesk-env:latest
```

### Connect With the Typed Client

```python
from supportdesk_env import SupportDeskAction, SupportDeskEnv

with SupportDeskEnv(base_url="http://localhost:8000").sync() as env:
    result = env.reset()
    result = env.step(SupportDeskAction(operation="select_task", task_id="task_easy_password_reset"))
    print(result.observation.task_title)
```

## Baselines

### Deterministic Reference Trajectories

The gold trajectories encoded in `tests/` and mirrored by the environment's hidden rubric achieve:

| Task | Score |
| --- | ---: |
| Easy | 1.00 |
| Medium | 1.00 |
| Hard | 1.00 |
| Average | 1.00 |

These are useful as a smoke-test ceiling and verify grader determinism.

### OpenAI Baseline

`inference.py` runs an OpenAI-compatible chat model against the environment in fixed task order with `temperature=0` for reproducibility. Set:

- `API_BASE_URL`
- `MODEL_NAME`
- `HF_TOKEN` or `OPENAI_API_KEY`

Then run:

```bash
uv run python inference.py
```

The script prints per-task scores and an average score. If `ENV_BASE_URL` is unset, it will try to launch `supportdesk-env:latest` locally through the OpenEnv client.

## Hugging Face Space Deployment

This repository is already structured as a Docker Space. After logging in and setting `HF_TOKEN`, push with the OpenEnv CLI:

```bash
uv run openenv push --repo-id <your-org>/supportdesk-env
```

The resulting Space should expose:

- `/health`
- `/reset`
- `/step`
- `/state`
- `/web`

## Notes

- The environment is fully deterministic. No randomness is used after task selection.
- The hidden rubric is kept server-side only; `state()` exposes operational state but not answer keys.
- The project is designed to run within the target constraint of 2 vCPU and 8 GB RAM.
