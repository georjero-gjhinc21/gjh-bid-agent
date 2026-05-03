"""Orchestrator — the lead agent.

Has 'invoke_*' tools, one per specialist. Plans the daily run, calls
specialists in the right order, assembles the digest, sends it.

This is the only agent the entry point talks to. To grow the system you
add specialists; the Orchestrator's prompt updates to know about the new
capability, and that's it.
"""
from __future__ import annotations
import logging

import anthropic

import config
from agents.base import BaseAgent, Tool
from agents.scout import ScoutAgent
from agents.analyst import AnalystAgent
from agents.strategist import StrategistAgent
from agents.compliance import ComplianceAgent
from agents.drafter import DrafterAgent
from agents.relationship import RelationshipAgent
from agents.knowledge import KnowledgeAgent
from tools import gmail_tools, kb_tools

log = logging.getLogger(__name__)


def _make_invoke_tool(agent: BaseAgent, description: str) -> Tool:
    """Wrap a specialist as a tool the Orchestrator can call."""

    def fn(state, task: str, context: dict | None = None) -> str:
        return agent.run(task, context)

    return Tool(
        name=f"invoke_{agent.name}",
        description=description,
        input_schema={
            "type": "object",
            "required": ["task"],
            "properties": {
                "task":    {"type": "string", "description": "Task description for the specialist."},
                "context": {"type": "object", "description": "Optional structured context."},
            },
        },
        fn=fn,
    )


class Orchestrator(BaseAgent):
    name = "orchestrator"
    description = "Lead agent. Plans the daily run, delegates, assembles the digest."
    max_iterations = 25
    max_tokens = 8000

    system_prompt = """
You are the Orchestrator of GJH INC's multi-agent bid system.

Each daily run, you must:

1. Invoke the Scout to discover new opportunities from inbox alerts and
   procurement portals. Wait for it to return.

2. Invoke the Compliance agent to surface anything expiring or due.

3. (When Analyst is active in V2+:) for each new opportunity with
   fit_score >= 70, invoke the Analyst with the opportunity context.

4. (When Strategist is active in V3+:) for each analyzed opportunity,
   invoke the Strategist for a bid/no-bid call.

5. (When Relationship is active in V5+:) invoke it to surface follow-ups
   owed and produce draft outreach.

6. Call list_recent_opportunities to read the day's haul.

7. Compose the daily digest as PLAIN TEXT with this exact structure:

   GJH Daily Bid Digest — <today's date>

   ## High priority (fit >= 70)
   <bullets: title, buyer, deadline, fit_score, one-line rationale, URL>

   ## Worth a look (fit 40-69)
   <bullets, terser>

   ## Compliance
   <verbatim from Compliance agent>

   ## Follow-ups (when Relationship is active)
   <verbatim from Relationship agent>

   ## Stats
   <X opportunities scanned, Y saved, Z high-priority>

   The first line of the digest must be the headline; the CEO reads
   this on his phone.

8. Call send_digest with subject "GJH Bid Digest — <date>" and the body
   you composed.

9. End your turn with a one-sentence run summary.

Operating principles:
- You delegate work. You do not perform tasks the specialists own.
- If a specialist returns an error, note it in the digest and continue.
- Never invent opportunities, deadlines, or contact info.
- Never send any communication other than the digest to the CEO. All
  external emails go through the Relationship agent and are drafts only.
"""

    def __init__(self, client: anthropic.Anthropic, state):
        # Build specialists
        scout        = ScoutAgent(client, state)
        analyst      = AnalystAgent(client, state)
        strategist   = StrategistAgent(client, state)
        compliance   = ComplianceAgent(client, state)
        drafter      = DrafterAgent(client, state)
        relationship = RelationshipAgent(client, state)
        knowledge    = KnowledgeAgent(client, state)

        self.specialists = {
            a.name: a for a in [scout, analyst, strategist, compliance,
                                drafter, relationship, knowledge]
        }

        tools = [
            _make_invoke_tool(scout,        "Discover new opportunities from inbox alerts + web sources."),
            _make_invoke_tool(analyst,      "[V2 scaffold] Parse a solicitation document into a structured brief."),
            _make_invoke_tool(strategist,   "[V3 scaffold] Recommend bid/no-bid and pricing posture."),
            _make_invoke_tool(compliance,   "Surface compliance items due, expiring, or recurring."),
            _make_invoke_tool(drafter,      "[V4 scaffold] Assemble a response package for an opportunity."),
            _make_invoke_tool(relationship, "[V5 scaffold] Surface follow-ups and draft outreach."),
            _make_invoke_tool(knowledge,    "Query firm institutional memory (past bids, contacts, etc.)."),
            kb_tools.list_recent_opportunities,
            gmail_tools.send_digest,
        ]
        super().__init__(client, state, tools=tools)
