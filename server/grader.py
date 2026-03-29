"""Deterministic grading utilities for supportdesk_env."""

from __future__ import annotations

import re
from typing import Iterable

try:
    from ..models import DraftState, RewardBreakdown
except ImportError:  # pragma: no cover - source-tree fallback
    from models import DraftState, RewardBreakdown

COMPONENT_WEIGHTS = {
    "evidence_score": 0.15,
    "queue_score": 0.15,
    "priority_score": 0.10,
    "tags_score": 0.15,
    "resolution_score": 0.15,
    "internal_note_score": 0.10,
    "reply_score": 0.15,
    "completion_score": 0.05,
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]+", text.lower()))


def _score_exact(actual: str | None, expected: str) -> float:
    return 1.0 if actual == expected else 0.0


def _score_tag_set(actual: Iterable[str], expected: Iterable[str]) -> float:
    actual_set = {item.strip().lower() for item in actual if item.strip()}
    expected_set = {item.strip().lower() for item in expected if item.strip()}
    if not actual_set and not expected_set:
        return 1.0
    if not actual_set or not expected_set:
        return 0.0
    intersection = len(actual_set & expected_set)
    union = len(actual_set | expected_set)
    return intersection / union


def _score_keyword_groups(text: str, keyword_groups: list[list[str]]) -> float:
    if not keyword_groups:
        return 1.0
    normalized = _normalize(text)
    matched = 0
    for group in keyword_groups:
        if all(keyword.lower() in normalized for keyword in group):
            matched += 1
    return matched / len(keyword_groups)


def _contains_forbidden(text: str, forbidden_terms: list[str]) -> bool:
    normalized = _normalize(text)
    return any(term.lower() in normalized for term in forbidden_terms)


def evaluate_task_progress(
    task: dict,
    draft: DraftState,
    opened_resource_ids: Iterable[str],
    discovered_resource_ids: Iterable[str],
    submitted: bool,
    previous_score: float = 0.0,
    action_penalty: float = 0.0,
) -> RewardBreakdown:
    """Evaluate the current workspace against the hidden rubric."""

    rubric = task["rubric"]
    required_resources = set(rubric["required_resources"])
    opened_set = set(opened_resource_ids)
    discovered_set = set(discovered_resource_ids)

    opened_fraction = (
        len(opened_set & required_resources) / len(required_resources)
        if required_resources
        else 1.0
    )
    discovered_fraction = (
        len(discovered_set & required_resources) / len(required_resources)
        if required_resources
        else 1.0
    )
    evidence_score = min(1.0, (0.7 * opened_fraction) + (0.3 * discovered_fraction))
    queue_score = _score_exact(draft.queue, rubric["queue"])
    priority_score = _score_exact(draft.priority, rubric["priority"])
    tags_score = _score_tag_set(draft.tags, rubric["tags"])
    resolution_score = _score_exact(draft.resolution_code, rubric["resolution_code"])
    internal_note_score = _score_keyword_groups(
        draft.internal_note,
        rubric["internal_note_keyword_groups"],
    )
    reply_score = _score_keyword_groups(draft.reply, rubric["reply_keyword_groups"])
    if _contains_forbidden(draft.reply, rubric["reply_forbidden_terms"]):
        reply_score = max(0.0, reply_score - 0.5)
    completion_score = 1.0 if submitted else 0.0

    weighted_partial = sum(
        COMPONENT_WEIGHTS[field] * value
        for field, value in {
            "evidence_score": evidence_score,
            "queue_score": queue_score,
            "priority_score": priority_score,
            "tags_score": tags_score,
            "resolution_score": resolution_score,
            "internal_note_score": internal_note_score,
            "reply_score": reply_score,
            "completion_score": completion_score,
        }.items()
    )
    partial_score = round(min(1.0, max(0.0, weighted_partial)), 6)
    score_delta = round(partial_score - previous_score, 6)
    final_reward = round(score_delta - action_penalty, 6)
    return RewardBreakdown(
        partial_score=partial_score,
        previous_score=round(previous_score, 6),
        score_delta=score_delta,
        action_penalty=round(action_penalty, 6),
        final_reward=final_reward,
        evidence_score=round(evidence_score, 6),
        queue_score=round(queue_score, 6),
        priority_score=round(priority_score, 6),
        tags_score=round(tags_score, 6),
        resolution_score=round(resolution_score, 6),
        internal_note_score=round(internal_note_score, 6),
        reply_score=round(reply_score, 6),
        completion_score=round(completion_score, 6),
    )
