"""Deterministic task fixtures for the support desk environment."""

from __future__ import annotations

TASKS = [
    {
        "task_id": "task_easy_password_reset",
        "difficulty": "easy",
        "title": "Expired password reset link",
        "customer_summary": "User cannot log in because their reset email expired before they clicked it.",
        "customer_message": (
            "Hi support, I requested a password reset for my AtlasCRM account last night, "
            "but by the time I opened the email the link said it was expired. I tried an older "
            "reset email too and got the same result. Can you help me get back in?"
        ),
        "resources": [
            {
                "resource_id": "doc_reset_policy",
                "kind": "kb_article",
                "title": "Password reset workflow",
                "summary": "Explains how fresh reset links work and when old links become invalid.",
                "content": (
                    "Whenever a customer requests a password reset, the platform issues a fresh reset "
                    "link. Each link expires after 30 minutes. Older reset emails are invalidated as soon "
                    "as a newer reset email is sent. Agents should never ask a customer to share a password."
                ),
                "key_facts": [
                    "Fresh reset links expire after 30 minutes.",
                    "Older reset emails become invalid once a newer email is sent.",
                    "Never ask the customer to share their password.",
                ],
            },
            {
                "resource_id": "doc_account_access_routing",
                "kind": "playbook",
                "title": "Queue routing for access issues",
                "summary": "Routing guide for login failures, MFA problems, and password reset issues.",
                "content": (
                    "Route password reset and login-access issues to the account_access queue. Use normal "
                    "priority unless there is evidence of a lockout affecting an executive or outage."
                ),
                "key_facts": [
                    "Password reset issues go to account_access.",
                    "Default priority is normal.",
                ],
            },
            {
                "resource_id": "record_aida_account",
                "kind": "account_record",
                "title": "Account snapshot: Aida Johnson",
                "summary": "Recent password reset activity for the affected customer.",
                "content": (
                    "Customer: Aida Johnson\nWorkspace: AtlasCRM\nRecent password reset requests: 2\n"
                    "Latest reset email sent: 11 hours ago\nStatus: no suspicious login activity detected."
                ),
                "key_facts": [
                    "Two recent password reset requests were sent.",
                    "No suspicious login activity detected.",
                ],
            },
        ],
        "rubric": {
            "queue": "account_access",
            "priority": "normal",
            "tags": ["password_reset", "login_issue"],
            "resolution_code": "send_reset_link",
            "required_resources": ["doc_reset_policy", "doc_account_access_routing"],
            "internal_note_keyword_groups": [
                ["fresh", "reset", "link"],
                ["older", "email"],
            ],
            "reply_keyword_groups": [
                ["fresh", "reset", "link"],
                ["30", "minute"],
                ["older", "email"],
            ],
            "reply_forbidden_terms": ["password"],
        },
    },
    {
        "task_id": "task_medium_duplicate_charge",
        "difficulty": "medium",
        "title": "Duplicate charge after plan upgrade",
        "customer_summary": "Customer believes they were charged twice after moving from Team to Business.",
        "customer_message": (
            "Hello, we upgraded from Team to Business this morning and our finance lead now sees two "
            "card charges that look almost identical. We need to know if this is a duplicate charge and "
            "whether you can reverse it immediately."
        ),
        "resources": [
            {
                "resource_id": "doc_billing_upgrade_holds",
                "kind": "billing_playbook",
                "title": "Upgrade billing hold policy",
                "summary": "Explains why card authorizations can appear alongside settled invoices.",
                "content": (
                    "During plan upgrades, the card network may show a temporary authorization hold "
                    "separately from the final settled invoice. The hold usually disappears within 3 to 5 "
                    "business days. Agents must not promise an immediate refund unless billing confirms a duplicate settlement."
                ),
                "key_facts": [
                    "Authorization holds are not settled charges.",
                    "Holds usually clear within 3 to 5 business days.",
                    "Do not promise an immediate refund.",
                ],
            },
            {
                "resource_id": "record_invoice_ledger",
                "kind": "invoice_record",
                "title": "Invoice ledger for Northwind Robotics",
                "summary": "Current billing ledger for the customer workspace.",
                "content": (
                    "Workspace: Northwind Robotics\nSettled invoice: INV-1048 for Business annual plan\n"
                    "Card authorization hold: INV-1049 pending, same card suffix 4421\nNo duplicate settled invoice detected."
                ),
                "key_facts": [
                    "INV-1048 is settled.",
                    "INV-1049 is a pending authorization hold.",
                    "No duplicate settled invoice exists.",
                ],
            },
            {
                "resource_id": "doc_billing_queue_matrix",
                "kind": "playbook",
                "title": "Queue matrix for payment incidents",
                "summary": "Priority and queue recommendations for billing disputes.",
                "content": (
                    "Route customer-reported duplicate charges and invoice confusion to the billing queue. "
                    "Use high priority when the customer references card charges or a finance blocker."
                ),
                "key_facts": [
                    "Duplicate-charge concerns route to billing.",
                    "Finance-blocking card issues are high priority.",
                ],
            },
        ],
        "rubric": {
            "queue": "billing",
            "priority": "high",
            "tags": ["duplicate_charge", "plan_upgrade"],
            "resolution_code": "explain_authorization_hold",
            "required_resources": [
                "doc_billing_upgrade_holds",
                "record_invoice_ledger",
                "doc_billing_queue_matrix",
            ],
            "internal_note_keyword_groups": [
                ["inv-1048"],
                ["inv-1049"],
                ["authorization", "hold"],
            ],
            "reply_keyword_groups": [
                ["authorization", "hold"],
                ["settled", "charge"],
                ["3", "5", "business", "day"],
            ],
            "reply_forbidden_terms": [
                "immediate refund",
                "refund today",
                "we refunded",
            ],
        },
    },
    {
        "task_id": "task_hard_security_incident",
        "difficulty": "hard",
        "title": "Enterprise security incident with billing anomaly",
        "customer_summary": "Enterprise admin reports suspicious API token activity, seat spikes, and billing risk.",
        "customer_message": (
            "Urgent: We are seeing a burst of API activity from a token our team does not recognize, "
            "our seat count jumped overnight, and billing now shows a much larger projected invoice. "
            "Please freeze anything risky and tell us what happens next."
        ),
        "resources": [
            {
                "resource_id": "doc_security_runbook",
                "kind": "security_playbook",
                "title": "Security response runbook",
                "summary": "Required first-response steps for suspicious token usage.",
                "content": (
                    "If a customer reports suspicious API token activity, revoke the exposed token, escalate "
                    "to account security, and preserve the incident timeline. Never ask the customer to send passwords. "
                    "Coordinate with billing only after the security triage is started."
                ),
                "key_facts": [
                    "Revoke the exposed token.",
                    "Escalate to account security.",
                    "Do not ask for passwords.",
                ],
            },
            {
                "resource_id": "doc_enterprise_sla",
                "kind": "sla_policy",
                "title": "Enterprise incident SLA",
                "summary": "Response-time policy for enterprise security incidents.",
                "content": (
                    "Enterprise security incidents require urgent priority and a one-hour first-response SLA. "
                    "The assigned queue is account_security."
                ),
                "key_facts": [
                    "Urgent priority is required.",
                    "First response SLA is one hour.",
                    "Queue is account_security.",
                ],
            },
            {
                "resource_id": "doc_billing_review_freeze",
                "kind": "billing_policy",
                "title": "Billing review freeze policy",
                "summary": "How billing reviews are paused during active incident investigations.",
                "content": (
                    "During a verified security incident, billing may place an internal review freeze on "
                    "the disputed usage while the investigation is active. Agents must not promise refunds before the review completes."
                ),
                "key_facts": [
                    "Billing review freeze may be applied.",
                    "Do not promise refunds before review completes.",
                ],
            },
            {
                "resource_id": "record_enterprise_audit_log",
                "kind": "audit_log",
                "title": "Enterprise audit snapshot",
                "summary": "Recent audit events from the affected workspace.",
                "content": (
                    "Workspace: Summit Peak Health\nSuspicious token: tok_prod_3921\nSeat count changed from 42 to 137 in 9 hours\n"
                    "Projected invoice impact: +$18,400\nAdmin reports the token is unrecognized."
                ),
                "key_facts": [
                    "Suspicious token is tok_prod_3921.",
                    "Seat count changed from 42 to 137.",
                    "Projected invoice impact is +$18,400.",
                ],
            },
        ],
        "rubric": {
            "queue": "account_security",
            "priority": "urgent",
            "tags": ["security_incident", "billing_anomaly", "enterprise_sla"],
            "resolution_code": "security_escalation",
            "required_resources": [
                "doc_security_runbook",
                "doc_enterprise_sla",
                "doc_billing_review_freeze",
                "record_enterprise_audit_log",
            ],
            "internal_note_keyword_groups": [
                ["tok_prod_3921"],
                ["42", "137"],
                ["billing", "review", "freeze"],
            ],
            "reply_keyword_groups": [
                ["revoke", "token"],
                ["security", "escalation"],
                ["billing", "review", "freeze"],
                ["one", "hour"],
            ],
            "reply_forbidden_terms": [
                "password",
                "share your password",
                "guaranteed refund",
                "immediate refund",
            ],
        },
    },
]

TASK_INDEX = {task["task_id"]: task for task in TASKS}
