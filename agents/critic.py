"""CriticAgent — evaluates deliverables against success criteria.

After each step completion, CriticAgent evaluates the output:
- Uses adversarial prompt: "Find what is wrong, missing, or weak"
- Returns issues with severity (low/medium/high/critical)
- If severity >= medium, step is sent back for retry (max 3 loops)
- Critiques logged to knowledge/critiques/ for learning
"""
from __future__ import annotations
import json
import logging
from datetime import datetime
from pathlib import Path

import anthropic

from agents.base import BaseAgent, Tool
import config

log = logging.getLogger(__name__)

CRITIC_INSTRUCTIONS = """
You are the CriticAgent — an adversarial reviewer for bid deliverables.

Your job is to FIND WHAT IS WRONG, MISSING, OR WEAK in a deliverable.
You are NOT friendly — you challenge assumptions and surface risks.

## YOUR PROCESS
1. Read the deliverable and its success_criteria
2. Identify issues, categorizing each by severity:
   - CRITICAL: Will cause bid rejection (missing attachment, wrong format, etc.)
   - HIGH: Major weakness that hurt scoring significantly
   - MEDIUM: Notable gap or inconsistency
   - LOW: Minor issue, acceptable with notes
3. For each issue, provide specific recommendation
4. Return JSON with issues and overall verdict

## OUTPUT FORMAT
```json
{
  "verdict": "PASS" | "REVISE" | "FAIL",
  "score": 85,
  "issues": [
    {
      "severity": "HIGH",
      "category": "compliance|gap|inconsistency|weakness",
      "description": "Issue description",
      "recommendation": "How to fix",
      "location": "Where in deliverable"
    }
  ],
  "passed_criteria": ["criterion 1", "criterion 2"],
  "failed_criteria": ["criterion 3"]
}
```

## SEVERITY DECISION
- PASS: No issues above LOW, all critical criteria met
- REVISE: Issues with severity >= MEDIUM, fixable
- FAIL: Critical issues that cannot be fixed in time, or major compliance failure
"""


def evaluate_deliverable(
    state,
    deliverable: str,
    success_criteria: list[str],
    step_name: str,
    step_goal: str
) -> str:
    """Tool: Evaluate a deliverable against success criteria."""
    log.info("[critic] evaluating: %s", step_name)
    
    return json.dumps({
        "status": "evaluation_complete",
        "step_name": step_name,
        "note": "Use CriticAgent for full evaluation"
    })


class CriticAgent(BaseAgent):
    name = "critic"
    description = "Adversarial reviewer — finds what's wrong in deliverables."
    max_iterations = 10
    max_tokens = 4000

    system_prompt = CRITIC_INSTRUCTIONS

    def __init__(self, client: anthropic.Anthropic, state):
        tools = [
            Tool(
                name="evaluate_deliverable",
                description="Evaluate a deliverable against success criteria",
                input_schema={
                    "type": "object",
                    "required": ["deliverable", "success_criteria", "step_name", "step_goal"],
                    "properties": {
                        "deliverable": {"type": "string", "description": "The deliverable content to evaluate"},
                        "success_criteria": {"type": "array", "items": {"type": "string"}, "description": "Success criteria to check against"},
                        "step_name": {"type": "string", "description": "Name of the step"},
                        "step_goal": {"type": "string", "description": "Goal of the step"},
                    },
                },
                fn=evaluate_deliverable,
            ),
        ]
        super().__init__(client, state, tools=tools)

    def build_input(self, task: str, context: dict | None = None) -> str:
        """Build input with success criteria context."""
        if not context:
            return task
        
        success_criteria = context.get("success_criteria", [])
        step_goal = context.get("step_goal", "")
        step_name = context.get("step_name", "")
        deliverable = context.get("deliverable", "")
        
        criteria_text = "\n".join(f"- {c}" for c in success_criteria)
        
        return f"""{task}

## Step Details
- Name: {step_name}
- Goal: {step_goal}

## Success Criteria
{criteria_text}

## Deliverable to Evaluate
{deliverable[:3000]}

Provide your adversarial review in JSON format.
"""

    def evaluate(
        self,
        deliverable: str,
        success_criteria: list[str],
        step_name: str,
        step_goal: str
    ) -> dict:
        """Synchronous evaluation without tool use loop."""
        criteria_text = "\n".join(f"- {c}" for c in success_criteria)
        
        prompt = f"""Evaluate this deliverable for the step "{step_name}".

Goal: {step_goal}

Success Criteria:
{criteria_text}

Deliverable:
{deliverable[:3000]}

Provide your adversarial review as JSON with keys:
- verdict: PASS | REVISE | FAIL
- score: 0-100
- issues: array of {{severity, category, description, recommendation, location}}
- passed_criteria: list
- failed_criteria: list
"""
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=self._full_system_prompt(),
            messages=[{"role": "user", "content": prompt}]
        )
        
        content = self._extract_text(response.content)
        
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            result = {
                "verdict": "REVISE",
                "score": 50,
                "issues": [{"severity": "HIGH", "description": "Failed to parse critic response", "recommendation": "Retry"}],
                "raw_response": content[:500]
            }
        
        return result

    def should_retry(self, evaluation: dict) -> bool:
        """Determine if step should be retried based on evaluation."""
        if evaluation.get("verdict") == "FAIL":
            return False
        
        for issue in evaluation.get("issues", []):
            if issue.get("severity") in ["CRITICAL", "HIGH", "MEDIUM"]:
                return True
        
        return False


def save_critique(
    workflow_id: str,
    step_id: str,
    evaluation: dict,
    deliverable: str
):
    """Save critique to knowledge/critiques/ for learning."""
    critiques_dir = Path(__file__).parent.parent / "knowledge" / "critiques"
    critiques_dir.mkdir(exist_ok=True)
    
    filename = f"{workflow_id}_{step_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    critique_data = {
        "workflow_id": workflow_id,
        "step_id": step_id,
        "timestamp": datetime.now().isoformat(),
        "evaluation": evaluation,
        "deliverable_preview": deliverable[:500]
    }
    
    (critiques_dir / filename).write_text(json.dumps(critique_data, indent=2))
    log.info("[critic] saved critique: %s", filename)