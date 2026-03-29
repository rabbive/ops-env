"""Tests for deterministic task grading."""

from __future__ import annotations

try:
    from supportdesk_env.models import DraftState
    from supportdesk_env.server.grader import evaluate_task_progress
    from supportdesk_env.server.task_data import TASK_INDEX
except ImportError:  # pragma: no cover - source-tree fallback
    from models import DraftState
    from server.grader import evaluate_task_progress
    from server.task_data import TASK_INDEX


def test_easy_gold_scores_one() -> None:
    task = TASK_INDEX["task_easy_password_reset"]
    draft = DraftState(
        queue="account_access",
        priority="normal",
        tags=["password_reset", "login_issue"],
        resolution_code="send_reset_link",
        internal_note=(
            "Customer needs a fresh reset link. Older email links are invalid once a newer reset "
            "email has been sent."
        ),
        reply=(
            "I have routed this as an account access issue and the next step is a fresh reset link. "
            "Please use the newest link within 30 minutes and ignore any older email reset links."
        ),
    )
    breakdown = evaluate_task_progress(
        task=task,
        draft=draft,
        opened_resource_ids=["doc_reset_policy", "doc_account_access_routing"],
        discovered_resource_ids=["doc_reset_policy", "doc_account_access_routing"],
        submitted=True,
    )
    assert breakdown.partial_score == 1.0


def test_medium_broken_submission_is_partial() -> None:
    task = TASK_INDEX["task_medium_duplicate_charge"]
    draft = DraftState(
        queue="general_support",
        priority="normal",
        tags=["billing_question"],
        resolution_code="request_more_info",
        internal_note="Customer says there might be a duplicate charge.",
        reply="We already refunded this and you should see it today.",
    )
    breakdown = evaluate_task_progress(
        task=task,
        draft=draft,
        opened_resource_ids=[],
        discovered_resource_ids=[],
        submitted=True,
    )
    assert 0.0 <= breakdown.partial_score < 0.25


def test_hard_reply_forbidden_terms_reduce_score() -> None:
    task = TASK_INDEX["task_hard_security_incident"]
    safe_draft = DraftState(
        queue="account_security",
        priority="urgent",
        tags=["security_incident", "billing_anomaly", "enterprise_sla"],
        resolution_code="security_escalation",
        internal_note=(
            "Escalate suspicious token tok_prod_3921, note seat jump from 42 to 137, and request "
            "a billing review freeze during investigation."
        ),
        reply=(
            "We are revoking the token now, opening a security escalation, applying a billing review "
            "freeze, and your enterprise first-response SLA is one hour."
        ),
    )
    risky_draft = safe_draft.model_copy(deep=True)
    risky_draft.reply += " Please send us your password for verification."
    safe = evaluate_task_progress(
        task=task,
        draft=safe_draft,
        opened_resource_ids=task["rubric"]["required_resources"],
        discovered_resource_ids=task["rubric"]["required_resources"],
        submitted=True,
    )
    risky = evaluate_task_progress(
        task=task,
        draft=risky_draft,
        opened_resource_ids=task["rubric"]["required_resources"],
        discovered_resource_ids=task["rubric"]["required_resources"],
        submitted=True,
    )
    assert safe.partial_score > risky.partial_score
