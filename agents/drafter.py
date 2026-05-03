"""Drafter agent — assembles bid response packages.

V1 status: scaffold. Activates in V4 once Analyst and Strategist are live
and the firm KB has the past-bid corpus indexed.

When active, the Drafter:
  - Pulls the right cover page (Attachment 1) pre-filled with GJH details.
  - Selects the right COI artifacts based on the RFQ insurance section.
  - Generates a tailored technical narrative from the master proposal,
    customized to the RFQ's stated scope.
  - Produces a draft pricing sheet with the Strategist's posture applied.
  - Bundles everything into a single zip ready for human review.

Nothing leaves the system without human signature.
"""
from agents.base import BaseAgent


class DrafterAgent(BaseAgent):
    name = "drafter"
    description = "Assembles bid response packages for human approval."

    system_prompt = """
You are the Drafter. Given an opportunity, its Analyst brief, and the
Strategist's posture, assemble the response package.

Mandatory inclusions for any MDCPS RFQ:
  - Attachment 1 (Cover Page) pre-filled with GJH details.
  - Current Hiscox COIs (Cyber + GL).
  - Foreign Country of Concern Attestation (Attachment 18).
  - Bidder's Preference (Attachment 7) — California section completed.
  - Technical narrative section relevant to the RFQ scope.
  - Pricing sheet aligned with Strategist's posture.

Output a JSON manifest of the package contents. The orchestrator emails
this manifest for human review before any submission happens.
"""

    def __init__(self, client, state):
        super().__init__(client, state, tools=[])
        # TODO V4: add fetch_template, render_cover_page, attach_coi, save_package
