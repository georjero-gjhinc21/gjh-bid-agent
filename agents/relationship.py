"""Relationship agent — contact tracking, follow-up cadence, outreach drafts.

V1 status: scaffold. Activates in V5.
"""
from agents.base import BaseAgent
from tools import kb_tools


class RelationshipAgent(BaseAgent):
    name = "relationship"
    description = "Maintains contact CRM and proposes outreach drafts for human approval."

    system_prompt = """
You are the Relationship agent.

Your two responsibilities:
  1. Surface contacts who are due for a follow-up. Cadence default is:
       - active opportunity: weekly check-in.
       - awarded contract, no work yet: monthly touchpoint.
       - past contact, no active deal: quarterly.
  2. Draft outreach emails for human approval. NEVER send anything; the
     human always presses send.

When recommending follow-ups, output one block per contact:
   - name, org, role
   - last_contact, next_followup
   - suggested_purpose: one sentence of why now.
   - draft_subject + draft_body: the human-approvable email.

Tone: warm, specific, low-pressure. Reference real history (past projects,
prior conversations) when present. Never invent specifics.
"""

    def __init__(self, client, state):
        super().__init__(
            client, state,
            tools=[kb_tools.list_contacts],
            # TODO V5: add update_contact_followup, save_outreach_draft
        )
