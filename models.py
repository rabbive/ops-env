"""Typed models for the Support Desk OpenEnv environment."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator

try:
    from .compat import Action, Observation, State
except ImportError:  # pragma: no cover - source-tree fallback
    from compat import Action, Observation, State

OperationName = Literal[
    "select_task",
    "search_docs",
    "open_resource",
    "set_priority",
    "set_queue",
    "set_tags",
    "set_resolution_code",
    "save_internal_note",
    "save_reply",
    "submit",
]

PriorityName = Literal["low", "normal", "high", "urgent"]
QueueName = Literal["account_access", "billing", "account_security", "general_support"]
ResolutionName = Literal[
    "send_reset_link",
    "explain_authorization_hold",
    "security_escalation",
    "request_more_info",
]


class TaskCard(BaseModel):
    """Visible task summary shown before selection."""

    task_id: str
    difficulty: str
    title: str
    customer_summary: str


class ResourceCard(BaseModel):
    """Compact resource metadata for the workbench."""

    resource_id: str
    kind: str
    title: str
    summary: str
    opened: bool = False


class ResourceDetail(BaseModel):
    """Expanded internal document content."""

    resource_id: str
    kind: str
    title: str
    content: str
    key_facts: list[str] = Field(default_factory=list)


class SearchResult(BaseModel):
    """Search result returned by the environment."""

    resource_id: str
    title: str
    snippet: str
    match_reasons: list[str] = Field(default_factory=list)


class DraftState(BaseModel):
    """Mutable ticket draft maintained across the episode."""

    queue: Optional[str] = None
    priority: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    resolution_code: Optional[str] = None
    internal_note: str = ""
    reply: str = ""


class RewardBreakdown(BaseModel):
    """Detailed scoring state used for reward shaping and debugging."""

    partial_score: float = 0.0
    previous_score: float = 0.0
    score_delta: float = 0.0
    action_penalty: float = 0.0
    final_reward: float = 0.0
    evidence_score: float = 0.0
    queue_score: float = 0.0
    priority_score: float = 0.0
    tags_score: float = 0.0
    resolution_score: float = 0.0
    internal_note_score: float = 0.0
    reply_score: float = 0.0
    completion_score: float = 0.0


class SupportDeskAction(Action):
    """Single action surface for support desk operations."""

    operation: OperationName = Field(..., description="Action type to execute.")
    task_id: Optional[str] = Field(default=None, description="Task identifier to select.")
    query: Optional[str] = Field(default=None, description="Search query for internal docs.")
    resource_id: Optional[str] = Field(default=None, description="Internal resource to open.")
    priority: Optional[PriorityName] = Field(default=None, description="Ticket priority.")
    queue: Optional[QueueName] = Field(default=None, description="Ticket routing queue.")
    tags: list[str] = Field(default_factory=list, description="Normalized ticket tags.")
    resolution_code: Optional[ResolutionName] = Field(
        default=None,
        description="Final resolution code.",
    )
    text: Optional[str] = Field(
        default=None,
        description="Free-text note or reply body depending on the operation.",
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        raw_tags = normalized.get("tags", []) or []
        deduped_tags = []
        for tag in raw_tags:
            clean_tag = str(tag).strip().lower()
            if clean_tag and clean_tag not in deduped_tags:
                deduped_tags.append(clean_tag)
        normalized["tags"] = deduped_tags
        if normalized.get("text") is not None:
            normalized["text"] = str(normalized["text"]).strip()
        return normalized

    @model_validator(mode="after")
    def validate_required_fields(self) -> "SupportDeskAction":
        required_by_operation = {
            "select_task": ("task_id",),
            "search_docs": ("query",),
            "open_resource": ("resource_id",),
            "set_priority": ("priority",),
            "set_queue": ("queue",),
            "set_tags": ("tags",),
            "set_resolution_code": ("resolution_code",),
            "save_internal_note": ("text",),
            "save_reply": ("text",),
            "submit": (),
        }
        required_fields = required_by_operation[self.operation]
        for field_name in required_fields:
            value = getattr(self, field_name)
            if value in (None, "", []):
                raise ValueError(f"{field_name} is required for operation '{self.operation}'")
        return self


class SupportDeskObservation(Observation):
    """Observation returned after reset and each step."""

    phase: str = "task_selection"
    instructions: str = ""
    available_tasks: list[TaskCard] = Field(default_factory=list)
    task_id: Optional[str] = None
    task_title: Optional[str] = None
    resource_catalog: list[ResourceCard] = Field(default_factory=list)
    open_resource: Optional[ResourceDetail] = None
    search_results: list[SearchResult] = Field(default_factory=list)
    current_draft: DraftState = Field(default_factory=DraftState)
    recent_feedback: list[str] = Field(default_factory=list)
    steps_remaining: int = 0
    score: float = 0.0
    reward_breakdown: Optional[RewardBreakdown] = None


class SupportDeskState(State):
    """Extended environment state available through state()."""

    phase: str = "task_selection"
    current_task_id: Optional[str] = None
    opened_resource_ids: list[str] = Field(default_factory=list)
    discovered_resource_ids: list[str] = Field(default_factory=list)
    search_history: list[str] = Field(default_factory=list)
    draft: DraftState = Field(default_factory=DraftState)
    action_history: list[dict[str, Any]] = Field(default_factory=list)
    last_score: float = 0.0
    submitted: bool = False
