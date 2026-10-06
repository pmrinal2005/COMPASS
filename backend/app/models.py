"""Typed data contracts shared by every agent (Pydantic)."""
from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


Lens = Literal["go", "pro"]


class EngineCall(BaseModel):
    """One planned SerpApi request (a 'Required Data Source' node)."""
    id: str = Field(default_factory=lambda: new_id("call_"))
    engine: str
    params: dict[str, Any]
    purpose: str = ""
    category: str = "generic"
    essential: bool = True


class Candidate(BaseModel):
    """A normalized option produced from any SerpApi engine."""
    id: str = Field(default_factory=lambda: new_id("cand_"))
    title: str
    category: str                      # flight | hotel | product | job | paper | patent | place | news | bundle
    engine: str
    source: str = ""                   # merchant / airline / publisher
    url: str | None = None
    price: float | None = None
    rating: float | None = None
    reviews: int | None = None
    duration_min: float | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    # verification / analysis annotations
    verified: bool = False
    corroborating_sources: list[str] = Field(default_factory=list)
    anomaly: str | None = None
    score: float | None = None
    breakdown: dict[str, float] = Field(default_factory=dict)


class DecisionNode(BaseModel):
    id: str
    kind: Literal["entity", "dimension", "constraint", "source", "action"]
    label: str
    meta: dict[str, Any] = Field(default_factory=dict)


class DecisionGraph(BaseModel):
    playbook_id: str
    intent: str
    lens: Lens
    slots: dict[str, Any]
    nodes: list[DecisionNode]
    calls: list[EngineCall]
    weights: dict[str, float]


class ActionProposal(BaseModel):
    id: str = Field(default_factory=lambda: new_id("act_"))
    session_id: str
    type: str                          # booking_flow | calendar_invite | document | notify | watch | email_rfq | application
    title: str
    description: str
    payload: dict[str, Any] = Field(default_factory=dict)
    risk: Literal["low", "medium", "high"] = "low"
    requires_approval: bool = True
    status: Literal["pending", "approved", "rejected", "executed", "failed", "modified"] = "pending"
    receipt: dict[str, Any] | None = None
    created_at: float = Field(default_factory=time.time)


class SessionRequest(BaseModel):
    prompt: str
    lens: Lens = "go"
    playbook_id: str | None = None
    priorities: dict[str, float] | None = None   # user-stated weight overrides
    auto_confirm: bool = False                   # skip budget confirmation


class ModifyRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
    note: str | None = None


class WatchRequest(BaseModel):
    session_id: str | None = None
    label: str
    engine: str
    params: dict[str, Any]
    target_title: str | None = None
    baseline_price: float | None = None
    threshold_pct: float = 8.0
    cadence_minutes: int = 30
