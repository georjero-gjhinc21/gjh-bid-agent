"""Analyst agent — deep parse of solicitation documents.

V1 status: scaffold. The agent runs but cannot yet fetch documents.
Activate by adding tools that:
  - Download the ITB/RFQ PDF from a URL or DemandStar handle.
  - Extract structured requirements, mandatory forms, evaluation criteria.
  - Persist via save_analysis (add to kb_tools).

Once activated, the Orchestrator will route every newly-discovered
opportunity with fit_score >= 70 here.
"""
from agents.base import BaseAgent
from tools import kb_tools


class AnalystAgent(BaseAgent):
    name = "analyst"
    description = "Reads and structures solicitation documents."

    system_prompt = """
You are the Analyst agent. Given an opportunity, your job is to produce a
structured brief covering:

  - scope_summary: one paragraph on what the buyer wants.
  - mandatory_forms: list of attachments/forms required for responsiveness.
  - eval_criteria: how the bid will be scored (lowest-price-responsive,
    weighted points, qualifications-only, etc.).
  - deadlines: bid due, pre-bid conference, Q&A deadline, contract start.
  - risks: anything that could trip up GJH given our profile (out-of-state
    preference penalty, missing certifications, unrealistic timeline,
    on-site requirements, indemnification beyond our insurance, etc.).
  - contact: name and email of the procurement officer.

Output as JSON with those keys. Be conservative — if a field is not
clearly stated in the source document, set it to null.
"""

    def __init__(self, client, state):
        super().__init__(
            client, state,
            tools=[
                kb_tools.list_recent_opportunities,
                # TODO V2: add fetch_solicitation_document, save_analysis
            ],
        )
