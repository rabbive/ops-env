"""Deterministic gold trajectories for reproducible baseline scores (no LLM)."""

from __future__ import annotations

try:
    from supportdesk_env.models import SupportDeskAction
    from supportdesk_env.server.supportdesk_environment import SupportDeskEnvironment
except ImportError:  # pragma: no cover - source-tree fallback
    from models import SupportDeskAction
    from server.supportdesk_environment import SupportDeskEnvironment


def run_easy_gold(env: SupportDeskEnvironment) -> float:
    env.reset()
    env.step(SupportDeskAction(operation="select_task", task_id="task_easy_password_reset"))
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
    obs = env.step(SupportDeskAction(operation="submit"))
    return float(obs.score)


def run_medium_gold(env: SupportDeskEnvironment) -> float:
    env.reset()
    env.step(SupportDeskAction(operation="select_task", task_id="task_medium_duplicate_charge"))
    env.step(
        SupportDeskAction(
            operation="search_docs",
            query="billing duplicate charge upgrade authorization hold invoice",
        )
    )
    env.step(SupportDeskAction(operation="open_resource", resource_id="doc_billing_upgrade_holds"))
    env.step(SupportDeskAction(operation="open_resource", resource_id="record_invoice_ledger"))
    env.step(SupportDeskAction(operation="open_resource", resource_id="doc_billing_queue_matrix"))
    env.step(SupportDeskAction(operation="set_queue", queue="billing"))
    env.step(SupportDeskAction(operation="set_priority", priority="high"))
    env.step(
        SupportDeskAction(
            operation="set_tags",
            tags=["duplicate_charge", "plan_upgrade"],
        )
    )
    env.step(
        SupportDeskAction(
            operation="set_resolution_code",
            resolution_code="explain_authorization_hold",
        )
    )
    env.step(
        SupportDeskAction(
            operation="save_internal_note",
            text=(
                "Settled invoice INV-1048 is posted; INV-1049 is still showing as an authorization "
                "hold rather than a settled charge."
            ),
        )
    )
    env.step(
        SupportDeskAction(
            operation="save_reply",
            text=(
                "The authorization hold on INV-1049 is separate from your settled charge INV-1048. "
                "Authorization holds typically clear within 3 to 5 business days while the card "
                "network processes activity."
            ),
        )
    )
    obs = env.step(SupportDeskAction(operation="submit"))
    return float(obs.score)


def run_hard_gold(env: SupportDeskEnvironment) -> float:
    env.reset()
    env.step(SupportDeskAction(operation="select_task", task_id="task_hard_security_incident"))
    env.step(
        SupportDeskAction(
            operation="search_docs",
            query="security billing token enterprise audit freeze sla revoke seat",
        )
    )
    env.step(SupportDeskAction(operation="open_resource", resource_id="doc_security_runbook"))
    env.step(SupportDeskAction(operation="open_resource", resource_id="doc_enterprise_sla"))
    env.step(SupportDeskAction(operation="open_resource", resource_id="doc_billing_review_freeze"))
    env.step(SupportDeskAction(operation="open_resource", resource_id="record_enterprise_audit_log"))
    env.step(SupportDeskAction(operation="set_queue", queue="account_security"))
    env.step(SupportDeskAction(operation="set_priority", priority="urgent"))
    env.step(
        SupportDeskAction(
            operation="set_tags",
            tags=["security_incident", "billing_anomaly", "enterprise_sla"],
        )
    )
    env.step(
        SupportDeskAction(
            operation="set_resolution_code",
            resolution_code="security_escalation",
        )
    )
    env.step(
        SupportDeskAction(
            operation="save_internal_note",
            text=(
                "Triage: suspicious token tok_prod_3921; seat count moved from 42 to 137; "
                "billing review freeze requested while security investigates."
            ),
        )
    )
    env.step(
        SupportDeskAction(
            operation="save_reply",
            text=(
                "We revoked the suspicious API token and opened a security escalation to "
                "account security under our one hour enterprise SLA, with a billing review freeze "
                "during the investigation. We will not request credentials in email."
            ),
        )
    )
    obs = env.step(SupportDeskAction(operation="submit"))
    return float(obs.score)


def run_all_scripted() -> dict[str, float]:
    """Run all three gold trajectories in-process; returns task_id -> final grader score."""
    env = SupportDeskEnvironment()
    scores = {
        "task_easy_password_reset": run_easy_gold(env),
        "task_medium_duplicate_charge": run_medium_gold(env),
        "task_hard_security_incident": run_hard_gold(env),
    }
    return scores
