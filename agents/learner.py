"""LearnerAgent — post-mortem and self-improvement.

Runs after every bid outcome (won/lost/withdrawn):
1. Reads full episodic log
2. Compares plan vs actual
3. Identifies decision points that mattered
4. Proposes updates to: knowledge/playbooks/*, prompts, workflow templates
5. Proposed updates go to knowledge/proposed_changes/ with diff + rationale

A human (or HITL approver) accepts or rejects. Accepted changes update knowledge base.
"""
from __future__ import annotations
import json
import logging
from datetime import datetime
from pathlib import Path

import anthropic

from agents.base import BaseAgent, Tool
from memory import get_memory_store
from knowledge import get_knowledge_store
import config

log = logging.getLogger(__name__)

LEARNER_INSTRUCTIONS = """
You are the LearnerAgent — you learn from bid outcomes and improve the system.

Your job is to perform a structured post-mortem after each bid and propose improvements.

## PROCESS
1. Read the full episodic log for the bid run
2. Compare planned workflow vs actual execution
3. Identify decision points that mattered
4. Extract lessons and propose concrete updates

## OUTPUT FORMAT
```json
{
  "post_mortem_id": "uuid",
  "bid_id": "ITB-XX-XXX-XXX",
  "outcome": "won|lost|withdrawn",
  "summary": "Brief summary of what happened",
  "decision_points": [
    {
      "point": "What decision was made",
      "alternatives": ["what else was considered"],
      "outcome_impact": "how it affected result"
    }
  ],
  "proposed_changes": [
    {
      "change_type": "playbook|prompt|template|workflow",
      "target": "path or name",
      "current": "current content",
      "proposed": "new content",
      "rationale": "why this improves things",
      "priority": "high|medium|low"
    }
  ],
  "lessons_learned": ["lesson 1", "lesson 2"]
}
```

## IMPORTANT
- Propose SPECIFIC changes, not vague improvements
- Include diff where possible
- Focus on actionable improvements that prevent future failures
"""


def run_post_mortem(state, bid_id: str, outcome: str, run_id: str) -> str:
    """Tool: Run post-mortem for a completed bid."""
    log.info("[learner] post-mortem for: %s (%s)", bid_id, outcome)
    
    memory = get_memory_store()
    store = get_knowledge_store()
    
    episodic = memory.get_episodic_log(run_id)
    
    return json.dumps({
        "status": "post_mortem_triggered",
        "bid_id": bid_id,
        "outcome": outcome,
        "episodic_events": len(episodic),
        "note": "Use LearnerAgent for full analysis"
    })


def list_proposed_changes(state) -> str:
    """Tool: List pending proposed changes."""
    changes_dir = Path(__file__).parent.parent / "knowledge" / "proposed_changes"
    
    changes = []
    for f in changes_dir.glob("*.json"):
        try:
            changes.append(json.loads(f.read_text()))
        except:
            pass
    
    return json.dumps({
        "count": len(changes),
        "changes": [{"id": c.get("id"), "type": c.get("change_type"), "priority": c.get("priority")} for c in changes]
    })


def approve_change(state, change_id: str) -> str:
    """Tool: Approve a proposed change (applies it to knowledge base)."""
    changes_dir = Path(__file__).parent.parent / "knowledge" / "proposed_changes"
    change_file = changes_dir / f"{change_id}.json"
    
    if not change_file.exists():
        return json.dumps({"status": "error", "message": "Change not found"})
    
    change = json.loads(change_file.read_text())
    
    store = get_knowledge_store()
    
    doc_id = f"learned/{change_id}"
    store.upsert(
        doc_id=doc_id,
        doc_type="lesson",
        title=f"Post-mortem: {change.get('bid_id', 'unknown')}",
        content=change.get("proposed", ""),
        tags=["learned", change.get("change_type", "unknown"), change.get("bid_id", "")]
    )
    
    change_file.rename(changes_dir / f"{change_id}_approved.json")
    
    return json.dumps({"status": "approved", "change_id": change_id})


def reject_change(state, change_id: str, reason: str) -> str:
    """Tool: Reject a proposed change."""
    changes_dir = Path(__file__).parent.parent / "knowledge" / "proposed_changes"
    change_file = changes_dir / f"{change_id}.json"
    
    if change_file.exists():
        change_file.rename(changes_dir / f"{change_id}_rejected.json")
    
    return json.dumps({"status": "rejected", "change_id": change_id, "reason": reason})


class LearnerAgent(BaseAgent):
    name = "learner"
    description = "Performs post-mortems and proposes knowledge base improvements."
    max_iterations = 12
    max_tokens = 5000

    system_prompt = LEARNER_INSTRUCTIONS

    def __init__(self, client: anthropic.Anthropic, state):
        tools = [
            Tool(
                name="run_post_mortem",
                description="Run post-mortem analysis for a completed bid",
                input_schema={
                    "type": "object",
                    "required": ["bid_id", "outcome", "run_id"],
                    "properties": {
                        "bid_id": {"type": "string", "description": "The solicitation ID"},
                        "outcome": {"type": "string", "description": "won|lost|withdrawn"},
                        "run_id": {"type": "string", "description": "The run ID to analyze"},
                    },
                },
                fn=run_post_mortem,
            ),
            Tool(
                name="list_proposed_changes",
                description="List pending proposed changes for review",
                input_schema={
                    "type": "object",
                    "properties": {},
                },
                fn=list_proposed_changes,
            ),
            Tool(
                name="approve_change",
                description="Approve and apply a proposed change to knowledge base",
                input_schema={
                    "type": "object",
                    "required": ["change_id"],
                    "properties": {
                        "change_id": {"type": "string", "description": "ID of change to approve"},
                    },
                },
                fn=approve_change,
            ),
            Tool(
                name="reject_change",
                description="Reject a proposed change",
                input_schema={
                    "type": "object",
                    "required": ["change_id", "reason"],
                    "properties": {
                        "change_id": {"type": "string", "description": "ID of change to reject"},
                        "reason": {"type": "string", "description": "Reason for rejection"},
                    },
                },
                fn=reject_change,
            ),
        ]
        super().__init__(client, state, tools=tools)

    def build_input(self, task: str, context: dict | None = None) -> str:
        """Build input with relevant memory."""
        if not context:
            return task
        
        memory = get_memory_store()
        
        bid_id = context.get("bid_id", "")
        run_id = context.get("run_id", memory.run_id)
        
        episodic = memory.get_episodic_log(run_id)
        
        episodic_text = f"## Episodic Log ({len(episodic)} events)\n"
        for e in episodic[:50]:
            episodic_text += f"- {e.get('timestamp')}: {e.get('event_type')}\n"
        
        return f"{task}\n\n{episodic_text}"


def create_proposed_change(post_mortem_result: dict) -> str:
    """Save proposed changes from post-mortem to proposed_changes/."""
    import uuid
    
    changes_dir = Path(__file__).parent.parent / "knowledge" / "proposed_changes"
    changes_dir.mkdir(exist_ok=True)
    
    change_id = str(uuid.uuid4())[:8]
    
    change_data = {
        "id": change_id,
        "timestamp": datetime.now().isoformat(),
        "bid_id": post_mortem_result.get("bid_id"),
        "outcome": post_mortem_result.get("outcome"),
        "summary": post_mortem_result.get("summary"),
        "decision_points": post_mortem_result.get("decision_points", []),
        "proposed_changes": post_mortem_result.get("proposed_changes", []),
        "lessons_learned": post_mortem_result.get("lessons_learned", []),
        "status": "pending_review"
    }
    
    (changes_dir / f"{change_id}.json").write_text(json.dumps(change_data, indent=2))
    log.info("[learner] saved proposed change: %s", change_id)
    
    return change_id