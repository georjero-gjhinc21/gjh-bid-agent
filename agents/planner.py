"""PlannerAgent — creates dynamic workflows for each solicitation.

Takes:
- solicitation_doc: the bid document content
- knowledge_base: retrieved playbooks and lessons
- prior_lessons: relevant past bid learnings

Produces:
- workflow as structured JSON with steps, each having:
  {id, name, goal, success_criteria, dependencies, agent_assigned, tools_needed}
"""
from __future__ import annotations
import json
import logging
from typing import Any

import anthropic

from agents.base import BaseAgent, Tool
from knowledge import get_knowledge_store
import config

log = logging.getLogger(__name__)

PLANNER_INSTRUCTIONS = """
You are the PlannerAgent — you create dynamic bid response workflows.

Given a solicitation document and knowledge base, you produce a WORKFLOW as JSON.
The workflow is DATA, not code — different solicitations get different plans.

## OUTPUT FORMAT
Produce a JSON workflow with this structure:
```json
{
  "workflow_id": "uuid",
  "solicitation_id": "ITB-XX-XXX-XXX",
  "title": "Brief title",
  "created_at": "ISO timestamp",
  "steps": [
    {
      "step_id": "1",
      "name": "Step name",
      "goal": "What this step achieves",
      "success_criteria": ["criterion 1", "criterion 2"],
      "dependencies": ["step_id_1", "step_id_2"],
      "agent_assigned": "bid_executor",
      "tools_needed": ["tool1", "tool2"],
      "estimated_duration_minutes": 30
    }
  ],
  "total_estimated_minutes": 180,
  "risk_flags": ["flag1", "flag2"]
}
```

## PLANNING PRINCIPLES
1. Each step must advance a sub-goal toward winning the bid
2. Dependencies must form a valid DAG (no cycles)
3. Steps should be small enough to complete in one agent turn
4. Include compliance checks early (fail-fast)
5. Save creative work (proposal writing) for later steps
6. Always include a final verification step before submission

## YOUR PROCESS
1. Parse the solicitation to understand requirements
2. Retrieve relevant playbooks and lessons
3. Identify critical fail-points specific to this solicitation
4. Build step list that addresses all requirements
5. Output the workflow JSON
"""


def create_workflow(state, solicitation_content: str, solicitation_id: str) -> str:
    """Tool: Generate a workflow for a solicitation."""
    log.info("[planner] creating workflow for: %s", solicitation_id)
    
    store = get_knowledge_store()
    relevant = store.retrieve(f"playbook for {solicitation_id}", top_k=3)
    lessons = store.retrieve("lessons from past bids", top_k=5)
    
    knowledge_summary = "## Relevant Knowledge:\n"
    for k in relevant:
        knowledge_summary += f"- {k['title']}: {k['content'][:200]}...\n"
    
    return json.dumps({
        "status": "workflow_generated",
        "solicitation_id": solicitation_id,
        "knowledge_used": len(relevant),
        "notes": "Use this with PlannerAgent to generate full workflow"
    })


class PlannerAgent(BaseAgent):
    name = "planner"
    description = "Creates dynamic bid response workflows from solicitation documents."
    max_iterations = 15
    max_tokens = 6000

    system_prompt = PLANNER_INSTRUCTIONS

    def __init__(self, client: anthropic.Anthropic, state):
        tools = [
            Tool(
                name="create_workflow",
                description="Generate a bid response workflow from solicitation content",
                input_schema={
                    "type": "object",
                    "required": ["solicitation_content", "solicitation_id"],
                    "properties": {
                        "solicitation_content": {"type": "string", "description": "The solicitation document text"},
                        "solicitation_id": {"type": "string", "description": "The solicitation ID (e.g., ITB-23-014-JW)"},
                    },
                },
                fn=create_workflow,
            ),
        ]
        super().__init__(client, state, tools=tools)

    def build_input(self, task: str, context: dict | None = None) -> str:
        """Build input with retrieved knowledge."""
        store = get_knowledge_store()
        
        solicitation_id = context.get("solicitation_id", "") if context else ""
        solicitation_content = context.get("solicitation_content", "") if context else ""
        
        relevant = store.retrieve(f"playbook for {solicitation_id}", top_k=3)
        lessons = store.retrieve("lessons", top_k=5)
        
        knowledge_section = "\n\n## Relevant Playbooks:\n"
        for k in relevant:
            knowledge_section += f"\n### {k['title']}\n{k['content'][:800]}\n"
        
        if lessons:
            knowledge_section += "\n\n## Past Lessons:\n"
            for l in lessons[:3]:
                knowledge_section += f"- {l['title']}: {l['content'][:200]}...\n"
        
        return f"{task}\n\n## Solicitation Content:\n{solicitation_content[:3000]}{knowledge_section}"