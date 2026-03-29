"""Core environment implementation for supportdesk_env."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Optional
from uuid import uuid4

try:
    from ..compat import Environment
    from ..models import (
        DraftState,
        ResourceCard,
        ResourceDetail,
        Reward,
        SearchResult,
        SupportDeskAction,
        SupportDeskObservation,
        SupportDeskState,
        TaskCard,
    )
    from .grader import evaluate_task_progress
    from .task_data import TASK_INDEX, TASKS
except ImportError:  # pragma: no cover - source-tree fallback
    from compat import Environment
    from models import (
        DraftState,
        ResourceCard,
        ResourceDetail,
        Reward,
        SearchResult,
        SupportDeskAction,
        SupportDeskObservation,
        SupportDeskState,
        TaskCard,
    )
    from server.grader import evaluate_task_progress
    from server.task_data import TASK_INDEX, TASKS


class SupportDeskEnvironment(Environment):
    """Deterministic support-triage environment."""

    def __init__(self, max_steps: int = 20):
        self.max_steps = max_steps
        self._state = SupportDeskState(episode_id=str(uuid4()), step_count=0)
        self._last_open_resource_id: Optional[str] = None
        self._last_search_results: list[SearchResult] = []
        self._recent_feedback: list[str] = []
        self._last_breakdown = evaluate_task_progress(
            task=TASKS[0],
            draft=DraftState(),
            opened_resource_ids=[],
            discovered_resource_ids=[],
            submitted=False,
        )

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        **_kwargs: Any,
    ) -> SupportDeskObservation:
        del seed
        self._state = SupportDeskState(
            episode_id=episode_id or str(uuid4()),
            step_count=0,
            phase="task_selection",
        )
        self._last_open_resource_id = None
        self._last_search_results = []
        self._recent_feedback = [
            "Select one of the available support tickets to begin the episode."
        ]
        self._last_breakdown = evaluate_task_progress(
            task=TASKS[0],
            draft=DraftState(),
            opened_resource_ids=[],
            discovered_resource_ids=[],
            submitted=False,
        )
        return self._build_observation(reward=0.0, done=False)

    def step(self, action: SupportDeskAction, **_kwargs: Any) -> SupportDeskObservation:
        if self._state.phase == "completed":
            self._recent_feedback = ["Episode already completed. Call reset() to start over."]
            return self._build_observation(reward=0.0, done=True)

        self._state.step_count += 1
        previous_score = self._state.last_score
        action_penalty = 0.0
        state_changed = False
        self._recent_feedback = []

        if self._is_repeated_action(action):
            action_penalty += 0.02
            self._recent_feedback.append("Repeated the same action without new evidence.")

        if action.operation == "select_task":
            state_changed, action_penalty = self._handle_select_task(action, action_penalty)
        elif action.operation == "search_docs":
            state_changed, action_penalty = self._handle_search_docs(action, action_penalty)
        elif action.operation == "open_resource":
            state_changed, action_penalty = self._handle_open_resource(action, action_penalty)
        elif action.operation == "set_priority":
            if not self._require_selected_task():
                action_penalty += 0.08
            else:
                self._state.draft.priority = action.priority
                self._recent_feedback.append(f"Priority set to {action.priority}.")
                state_changed = True
        elif action.operation == "set_queue":
            if not self._require_selected_task():
                action_penalty += 0.08
            else:
                self._state.draft.queue = action.queue
                self._recent_feedback.append(f"Queue set to {action.queue}.")
                state_changed = True
        elif action.operation == "set_tags":
            if not self._require_selected_task():
                action_penalty += 0.08
            else:
                self._state.draft.tags = list(action.tags)
                self._recent_feedback.append(f"Tags updated to {action.tags}.")
                state_changed = True
        elif action.operation == "set_resolution_code":
            if not self._require_selected_task():
                action_penalty += 0.08
            else:
                self._state.draft.resolution_code = action.resolution_code
                self._recent_feedback.append(
                    f"Resolution code set to {action.resolution_code}."
                )
                state_changed = True
        elif action.operation == "save_internal_note":
            if not self._require_selected_task():
                action_penalty += 0.08
            elif not action.text:
                action_penalty += 0.03
                self._recent_feedback.append("Internal note was empty and not saved.")
            else:
                self._state.draft.internal_note = action.text
                self._recent_feedback.append("Internal note saved.")
                state_changed = True
        elif action.operation == "save_reply":
            if not self._require_selected_task():
                action_penalty += 0.08
            elif not action.text:
                action_penalty += 0.03
                self._recent_feedback.append("Customer reply was empty and not saved.")
            else:
                self._state.draft.reply = action.text
                self._recent_feedback.append("Customer reply saved.")
                state_changed = True
        elif action.operation == "submit":
            if self._state.current_task_id is None:
                action_penalty += 0.05
                self._recent_feedback.append("Cannot submit before selecting a task.")
                self._state.phase = "completed"
                self._state.submitted = False
                state_changed = True
            else:
                missing_core_fields = any(
                    value in (None, "", [])
                    for value in (
                        self._state.draft.queue,
                        self._state.draft.priority,
                        self._state.draft.tags,
                        self._state.draft.resolution_code,
                        self._state.draft.reply,
                    )
                )
                if missing_core_fields:
                    action_penalty += 0.05
                    self._recent_feedback.append(
                        "Submitted before the draft was fully completed."
                    )
                else:
                    self._recent_feedback.append("Ticket submitted for final grading.")
                self._state.submitted = True
                self._state.phase = "completed"
                state_changed = True

        if not state_changed and not self._recent_feedback:
            self._recent_feedback.append("Action had no effect on the workspace.")

        self._append_action_history(action)

        breakdown = self._evaluate(previous_score=previous_score, action_penalty=action_penalty)
        self._state.last_score = breakdown.partial_score
        self._last_breakdown = breakdown

        done = self._state.phase == "completed"
        if self._state.step_count >= self.max_steps and not done:
            self._recent_feedback.append(
                "Step limit reached. Current draft was graded without an explicit submit."
            )
            done = True
            self._state.phase = "completed"
            self._state.submitted = False
            breakdown = self._evaluate(
                previous_score=previous_score,
                action_penalty=action_penalty,
            )
            self._state.last_score = breakdown.partial_score
            self._last_breakdown = breakdown

        return self._build_observation(reward=breakdown.final_reward, done=done)

    @property
    def state(self) -> SupportDeskState:
        return self._state

    def _handle_select_task(
        self,
        action: SupportDeskAction,
        action_penalty: float,
    ) -> tuple[bool, float]:
        if self._state.current_task_id is not None:
            self._recent_feedback.append("Task already selected. Use reset() for a new episode.")
            return False, action_penalty + 0.06
        task = TASK_INDEX.get(action.task_id or "")
        if task is None:
            self._recent_feedback.append("Unknown task_id.")
            return False, action_penalty + 0.08
        self._state.phase = "task_workbench"
        self._state.current_task_id = task["task_id"]
        self._state.opened_resource_ids = []
        self._state.discovered_resource_ids = []
        self._state.search_history = []
        self._state.draft = DraftState()
        self._state.submitted = False
        self._last_open_resource_id = None
        self._last_search_results = []
        self._recent_feedback.append(f"Loaded task '{task['title']}'.")
        return True, action_penalty

    def _handle_search_docs(
        self,
        action: SupportDeskAction,
        action_penalty: float,
    ) -> tuple[bool, float]:
        if not self._require_selected_task():
            return False, action_penalty + 0.08
        query = (action.query or "").strip()
        if not query:
            self._recent_feedback.append("Search query was empty.")
            return False, action_penalty + 0.03
        results, hit_ids = self._search_resources(query)
        self._last_search_results = results
        self._state.search_history.append(query)
        for resource_id in hit_ids:
            if resource_id not in self._state.discovered_resource_ids:
                self._state.discovered_resource_ids.append(resource_id)
        if results:
            self._recent_feedback.append(
                f"Search found {len(results)} relevant internal resources."
            )
        else:
            self._recent_feedback.append("Search found no matching internal resources.")
        return True, action_penalty

    def _handle_open_resource(
        self,
        action: SupportDeskAction,
        action_penalty: float,
    ) -> tuple[bool, float]:
        if not self._require_selected_task():
            return False, action_penalty + 0.08
        resource = self._get_resource(action.resource_id or "")
        if resource is None:
            self._recent_feedback.append("Unknown resource_id.")
            return False, action_penalty + 0.05
        self._last_open_resource_id = resource["resource_id"]
        if resource["resource_id"] not in self._state.opened_resource_ids:
            self._state.opened_resource_ids.append(resource["resource_id"])
        self._recent_feedback.append(f"Opened resource '{resource['title']}'.")
        return True, action_penalty

    def _require_selected_task(self) -> bool:
        if self._state.current_task_id is None:
            self._recent_feedback.append("Select a task before using workbench actions.")
            return False
        return True

    def _search_resources(self, query: str) -> tuple[list[SearchResult], list[str]]:
        task = self._current_task()
        if task is None:
            return [], []
        query_tokens = self._tokenize(query)
        ranked: list[tuple[int, dict]] = []
        for resource in task["resources"]:
            haystack = " ".join(
                [
                    resource["title"],
                    resource["summary"],
                    resource["content"],
                    " ".join(resource["key_facts"]),
                ]
            ).lower()
            score = sum(1 for token in query_tokens if token in haystack)
            if score:
                ranked.append((score, resource))
        ranked.sort(key=lambda item: (-item[0], item[1]["resource_id"]))
        results = []
        hit_ids = []
        for score, resource in ranked[:4]:
            hit_ids.append(resource["resource_id"])
            snippet = resource["summary"]
            match_reasons = [f"{score} query token(s) matched"]
            results.append(
                SearchResult(
                    resource_id=resource["resource_id"],
                    title=resource["title"],
                    snippet=snippet,
                    match_reasons=match_reasons,
                )
            )
        return results, hit_ids

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"[a-z0-9_]+", text.lower())

    def _current_task(self) -> Optional[dict]:
        if self._state.current_task_id is None:
            return None
        return TASK_INDEX[self._state.current_task_id]

    def _get_resource(self, resource_id: str) -> Optional[dict]:
        task = self._current_task()
        if task is None:
            return None
        for resource in task["resources"]:
            if resource["resource_id"] == resource_id:
                return resource
        return None

    def _append_action_history(self, action: SupportDeskAction) -> None:
        self._state.action_history.append(action.model_dump(exclude_none=True))
        self._state.action_history = self._state.action_history[-20:]

    def _is_repeated_action(self, action: SupportDeskAction) -> bool:
        if not self._state.action_history:
            return False
        previous = self._state.action_history[-1]
        current = action.model_dump(exclude_none=True)
        return previous == current

    def _evaluate(self, previous_score: float, action_penalty: float):
        task = self._current_task() or TASKS[0]
        return evaluate_task_progress(
            task=task,
            draft=self._state.draft,
            opened_resource_ids=self._state.opened_resource_ids,
            discovered_resource_ids=self._state.discovered_resource_ids,
            submitted=self._state.submitted,
            previous_score=previous_score,
            action_penalty=action_penalty,
        )

    def _build_observation(self, reward: float, done: bool) -> SupportDeskObservation:
        task = self._current_task()
        available_tasks = [
            TaskCard(
                task_id=item["task_id"],
                difficulty=item["difficulty"],
                title=item["title"],
                customer_summary=item["customer_summary"],
            )
            for item in TASKS
        ]
        resource_catalog = []
        open_resource = None
        if task is not None:
            resource_catalog = [
                ResourceCard(
                    resource_id=resource["resource_id"],
                    kind=resource["kind"],
                    title=resource["title"],
                    summary=resource["summary"],
                    opened=resource["resource_id"] in self._state.opened_resource_ids,
                )
                for resource in task["resources"]
            ]
            if self._last_open_resource_id is not None:
                resource = self._get_resource(self._last_open_resource_id)
                if resource is not None:
                    open_resource = ResourceDetail(
                        resource_id=resource["resource_id"],
                        kind=resource["kind"],
                        title=resource["title"],
                        content=resource["content"],
                        key_facts=deepcopy(resource["key_facts"]),
                    )
        return SupportDeskObservation(
            done=done,
            reward=reward,
            metadata={
                "score": self._state.last_score,
                "reward_breakdown": self._last_breakdown.model_dump(),
                "task_id": self._state.current_task_id,
            },
            phase=self._state.phase,
            instructions=self._build_instructions(task),
            available_tasks=available_tasks,
            task_id=self._state.current_task_id,
            task_title=task["title"] if task else None,
            resource_catalog=resource_catalog,
            open_resource=open_resource,
            search_results=deepcopy(self._last_search_results),
            current_draft=self._state.draft.model_copy(deep=True),
            recent_feedback=list(self._recent_feedback),
            steps_remaining=max(0, self.max_steps - self._state.step_count),
            score=self._state.last_score,
            reward_breakdown=self._last_breakdown,
            reward_detail=Reward(
                reward=reward,
                breakdown=self._last_breakdown,
            ),
        )

    def _build_instructions(self, task: Optional[dict]) -> str:
        if task is None:
            return (
                "Choose a support ticket. After selection, search docs, open relevant resources, "
                "set queue and priority, add tags, draft an internal note, draft a customer reply, "
                "and submit the final resolution."
            )
        return (
            f"Customer ticket: {task['customer_message']}\n"
            "Use the workbench to investigate internal documents, capture the right operational "
            "metadata, and write a safe customer reply. The final score rewards evidence gathering, "
            "correct routing, accurate tags, the right resolution code, strong notes, and a complete reply."
        )
