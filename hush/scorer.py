import math
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from hush.config import (
    CONSEQUENCE_WEIGHTS,
    T_HIGH,
    T_BRIEF,
)


def compute_decay(received_at_iso: str, deadline_at_iso: Optional[str]) -> float:
    """
    Decay factor: 1.0 - 3.0
    Formula: 1 + 2 / (1 + days_until_deadline)
    Returns 1.0 when no deadline is present or if deadline is unparseable.
    """
    if not deadline_at_iso:
        return 1.0

    try:
        received_dt = datetime.fromisoformat(received_at_iso)
        deadline_dt = datetime.fromisoformat(deadline_at_iso)

        diff_seconds = (deadline_dt - received_dt).total_seconds()
        days_until_deadline = max(0.0, diff_seconds / 86400.0)

        decay = 1.0 + (2.0 / (1.0 + days_until_deadline))
        return round(decay, 4)
    except Exception:
        return 1.0


def calculate_score(
    urgency: float,
    category: str,
    received_at_iso: str,
    deadline_at_iso: Optional[str] = None,
) -> Tuple[float, float, float]:
    """
    Deterministic scoring:
    score = urgency * consequence * decay
    Returns: (score, consequence, decay)
    """
    clamped_urgency = max(0.0, min(1.0, float(urgency)))
    consequence = CONSEQUENCE_WEIGHTS.get(category.lower(), 0.50)
    decay = compute_decay(received_at_iso, deadline_at_iso)

    raw_score = clamped_urgency * consequence * decay
    score = round(raw_score, 4)
    return score, consequence, decay


def route_decision(score: float, t_high: float = T_HIGH, t_brief: float = T_BRIEF) -> str:
    """
    Determines output path:
    - 'interrupt' if score >= T_high (default 0.55)
    - 'brief' if score >= T_brief (default 0.15)
    - 'reject' otherwise
    """
    if score >= t_high:
        return "interrupt"
    elif score >= t_brief:
        return "brief"
    else:
        return "reject"
