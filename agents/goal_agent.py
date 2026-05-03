"""GoalAgent — goal decomposition and sub-goal tracking.

Top-level goal lives in goals.yaml.
GoalAgent decomposes into sub-goals with measurable success criteria.
Every workflow step links to a sub-goal.
Sub-goal progress is tracked numerically (% complete, blockers, ETA).
"""
from __future__ import annotations
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

import config

log = logging.getLogger(__name__)

GOALS_FILE = Path(__file__).parent / "goals.yaml"


class GoalManager:
    """Manages goals and sub-goals."""

    def __init__(self, goals_file: str = str(GOALS_FILE)):
        self.goals_file = Path(goals_file)
        self.goals = self._load_goals()

    def _load_goals(self) -> list[dict]:
        if self.goals_file.exists():
            data = yaml.safe_load(self.goals_file.read_text())
            return data.get("goals", [])
        return []

    def save(self):
        """Save goals back to file."""
        self.goals_file.write_text(yaml.dump({"goals": self.goals}, default_flow_style=False))

    def get_goal(self, goal_id: str) -> dict | None:
        for g in self.goals:
            if g.get("id") == goal_id:
                return g
        return None

    def get_sub_goal(self, goal_id: str, sub_goal_id: str) -> dict | None:
        goal = self.get_goal(goal_id)
        if not goal:
            return None
        for sg in goal.get("sub_goals", []):
            if sg.get("id") == sub_goal_id:
                return sg
        return None

    def update_sub_goal_progress(self, goal_id: str, sub_goal_id: str, progress: int, blockers: list[str] = None):
        """Update sub-goal progress."""
        goal = self.get_goal(goal_id)
        if not goal:
            return
        
        for sg in goal.get("sub_goals", []):
            if sg.get("id") == sub_goal_id:
                sg["progress_percent"] = progress
                if blockers:
                    sg["blockers"] = blockers
                break
        
        self.save()
        log.info("[goals] updated %s/%s: %d%%", goal_id, sub_goal_id, progress)

    def complete_sub_goal(self, goal_id: str, sub_goal_id: str):
        """Mark sub-goal as complete."""
        self.update_sub_goal_progress(goal_id, sub_goal_id, 100)

    def link_step_to_sub_goal(self, step_id: str, sub_goal_id: str) -> dict:
        """Return metadata for a step linked to a sub-goal."""
        return {
            "step_id": step_id,
            "sub_goal_id": sub_goal_id,
            "timestamp": datetime.now().isoformat()
        }

    def get_progress_summary(self, goal_id: str) -> dict:
        """Get overall progress for a goal."""
        goal = self.get_goal(goal_id)
        if not goal:
            return {}
        
        sub_goals = goal.get("sub_goals", [])
        if not sub_goals:
            return {"total": 0, "completed": 0, "percent": 0}
        
        total = len(sub_goals)
        completed = sum(1 for sg in sub_goals if sg.get("progress_percent", 0) >= 100)
        percent = sum(sg.get("progress_percent", 0) for sg in sub_goals) / total
        
        return {"total": total, "completed": completed, "percent": round(percent, 1)}


_goal_manager: GoalManager | None = None


def get_goal_manager() -> GoalManager:
    """Get singleton GoalManager."""
    global _goal_manager
    if _goal_manager is None:
        _goal_manager = GoalManager()
    return _goal_manager