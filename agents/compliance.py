"""Compliance agent — watches certifications, COIs, filings, license renewals.

V1 status: partial. Reads the seeded compliance_items table and surfaces
anything due within the next 60 days, plus anything marked 'monthly'
that hasn't been done this month. Output goes into the daily digest.

Activate fully by adding tools that can:
  - File the MDCPS OEO monthly report (or draft it for human submission).
  - Check Sunbiz status for the Florida foreign-corp registration.
  - Fetch the latest COI on file at MDCPS Risk Management.
"""
from agents.base import BaseAgent
from tools import kb_tools


class ComplianceAgent(BaseAgent):
    name = "compliance"
    description = "Tracks COIs, licenses, monthly filings, and certification renewals."

    system_prompt = """
You are the Compliance agent. Your remit is to keep GJH from getting
bumped from any vendor pool for a paperwork lapse.

Each run:
1. Call list_compliance to see the tracked items.
2. Identify anything due within 60 days, anything marked "monthly" that
   could be missed, and anything where renews="unknown" (these need a
   human decision and should be flagged loudly).
3. For each finding, output:
     - item name
     - status: due_now | due_soon | recurring_due | unknown | ok
     - action: one-sentence concrete next step
     - owner: who needs to do it

Be terse. The Orchestrator will paste your output verbatim into the
digest under a "Compliance" header.

If everything is healthy, return exactly:  "All compliance items current."
"""

    def __init__(self, client, state):
        super().__init__(
            client, state,
            tools=[kb_tools.list_compliance],
        )
