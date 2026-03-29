"""End-to-end environment tests for supportdesk_env."""

from __future__ import annotations

try:
    from supportdesk_env.models import SupportDeskAction
    from supportdesk_env.server.supportdesk_environment import SupportDeskEnvironment
except ImportError:  # pragma: no cover - source-tree fallback
    from models import SupportDeskAction
    from server.supportdesk_environment import SupportDeskEnvironment


def _run_easy_gold(env: SupportDeskEnvironment):
    env.reset()
    observation = env.step(
        SupportDeskAction(operation="select_task", task_id="task_easy_password_reset")
    )
    assert observation.task_id == "task_easy_password_reset"
    env.step(SupportDeskAction(operation="search_docs", query="password reset access"))
    env.step(SupportDeskAction(operation="open_resource", resource_id="doc_reset_policy"))
    env.step(
        SupportDeskAction(operation="open_resource", resource_id="doc_account_access_routing")
    )
    env.step(SupportDeskAction(operation="set_queue", queue="account_access"))
    env.step(SupportDeskAction(operation="set_priority", priority="normal"))
    env.step(
        SupportDeskAction(
            operation="set_tags",
            tags=["password_reset", "login_issue"],
        )
    )
    env.step(
        SupportDeskAction(
            operation="set_resolution_code",
            resolution_code="send_reset_link",
        )
    )
    env.step(
        SupportDeskAction(
            operation="save_internal_note",
            text=(
                "Customer needs a fresh reset link. Older email links are invalid when a newer email "
                "has already been sent."
            ),
        )
    )
    env.step(
        SupportDeskAction(
            operation="save_reply",
            text=(
                "Please use the fresh reset link from the newest email within 30 minutes and ignore "
                "older email reset links."
            ),
        )
    )
    return env.step(SupportDeskAction(operation="submit"))


def test_reset_lists_three_tasks() -> None:
    env = SupportDeskEnvironment()
    observation = env.reset()
    assert observation.phase == "task_selection"
    assert len(observation.available_tasks) == 3
    assert observation.steps_remaining == env.max_steps


def test_state_updates_after_selection() -> None:
    env = SupportDeskEnvironment()
    env.reset()
    observation = env.step(
        SupportDeskAction(operation="select_task", task_id="task_medium_duplicate_charge")
    )
    state = env.state
    assert observation.phase == "task_workbench"
    assert state.current_task_id == "task_medium_duplicate_charge"
    assert state.step_count == 1


def test_easy_task_gold_trajectory_scores_one() -> None:
    env = SupportDeskEnvironment()
    observation = _run_easy_gold(env)
    assert observation.done is True
    assert observation.score == 1.0


def test_submit_without_task_finishes_with_low_score() -> None:
    env = SupportDeskEnvironment()
    env.reset()
    observation = env.step(SupportDeskAction(operation="submit"))
    assert observation.done is True
    assert observation.score == 0.0


def test_reward_progress_is_positive_for_meaningful_actions() -> None:
    env = SupportDeskEnvironment()
    env.reset()
    first = env.step(
        SupportDeskAction(operation="select_task", task_id="task_hard_security_incident")
    )
    second = env.step(SupportDeskAction(operation="search_docs", query="token security sla"))
    third = env.step(SupportDeskAction(operation="open_resource", resource_id="doc_security_runbook"))
    assert first.reward >= 0.0
    assert second.reward > 0.0
    assert third.reward > 0.0


def test_all_tasks_have_working_smoke_paths() -> None:
    env = SupportDeskEnvironment()
    for task_id, resource_id, queue, priority, tags, resolution in [
        (
            "task_easy_password_reset",
            "doc_reset_policy",
            "account_access",
            "normal",
            ["password_reset", "login_issue"],
            "send_reset_link",
        ),
        (
            "task_medium_duplicate_charge",
            "record_invoice_ledger",
            "billing",
            "high",
            ["duplicate_charge", "plan_upgrade"],
            "explain_authorization_hold",
        ),
        (
            "task_hard_security_incident",
            "record_enterprise_audit_log",
            "account_security",
            "urgent",
            ["security_incident", "billing_anomaly", "enterprise_sla"],
            "security_escalation",
        ),
    ]:
        env.reset()
        env.step(SupportDeskAction(operation="select_task", task_id=task_id))
        env.step(SupportDeskAction(operation="search_docs", query=task_id))
        env.step(SupportDeskAction(operation="open_resource", resource_id=resource_id))
        env.step(SupportDeskAction(operation="set_queue", queue=queue))
        env.step(SupportDeskAction(operation="set_priority", priority=priority))
        env.step(SupportDeskAction(operation="set_tags", tags=tags))
        env.step(
            SupportDeskAction(operation="set_resolution_code", resolution_code=resolution)
        )
        env.step(
            SupportDeskAction(
                operation="save_internal_note",
                text="Escalation context gathered from the relevant internal records.",
            )
        )
        observation = env.step(
            SupportDeskAction(
                operation="save_reply",
                text="We reviewed the case and are taking the documented next steps.",
            )
        )
        assert observation.task_id == task_id
