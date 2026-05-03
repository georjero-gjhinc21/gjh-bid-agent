"""BidExecutorAgent — orchestrates bid response for ITB-23-014-JW.

Implements the strategic playbook with clear workflow steps:
1. Compliance Audit (fail-points check)
2. Technical Proposal Enhancement
3. Submission Assembly
4. Pre-submission Final Check

This agent owns the end-to-end bid response for a specific solicitation.
"""
from __future__ import annotations
import json
import logging
from datetime import datetime
from typing import Any

import anthropic

from agents.base import BaseAgent, Tool
import config

log = logging.getLogger(__name__)


BID_PLAYBOOK = """
You are the BidExecutor for ITB-23-014-JW (Miami-Dade County Public Schools Website Development).

## AWARD MODEL - CRITICAL CONTEXT
This is NOT winner-takes-all. It's a PRE-APPROVED VENDOR POOL with two stages:
1. **Stage 1** — Get into the pool. Pricing is NOT evaluated. Award to "all responsive and responsible bidders."
   Your ONLY job is FLAWLESS COMPLIANCE.
2. **Stage 2** — RFQs over $1,000. Pool vendors get RFQs. Lowest responsive/responsible bidder wins each task.
   This is where you actually make money.

IMPLICATION: Don't over-engineer the technical proposal trying to "beat" competitors.
You only need to clear the responsiveness bar. Save persuasion for RFQ stage.

## RESPONSIVENESS CHECKLIST — THE FAIL-POINTS

Check each of these BEFORE submission:

1. **Attachment 1 (Cover Page)** — subcontractor field must be CONSISTENT.
   If Ikomet Technologies is the sub, it must be declared on EVERY copy.

2. **Attachment 7 (Bidder's Preference)** — California vendor with no Florida preference; mark accurately.

3. **Attachment 11 (Bidder Experience)** — three references required.
   REPLACE First Republic Bank reference — that bank FAILED and was seized by FDIC in May 2023.
   This is a serious red flag. Replace with a live, contactable reference (K-12, higher-ed, or government).

4. **Attachment 18 (Non-Foreign)** — Ikomet Technologies (India) is the declared subcontractor.
   Confirm India isn't triggering disclosure obligations under FL Statute 287.138.
   Verify the affidavit language is satisfied.

5. **Florida foreign corp authorization** — GJH is a California S-Corp.
   Must be registered with FL Division of Corporations (Sunbiz), not just DBE-certified.
   These are DIFFERENT filings. File CR2E007 if missing.

6. **Required documents** — verify all signed and dated within validity windows:
   - W-9
   - FM-3921 (Vendor App)
   - FM-7594
   - cr2e007 (Background Screening)
   - Coercion Affidavit
   - Vallejo business license

7. **Performance security** — not required at bid time, but know bonding capacity may be needed for RFQs >$200K.

## TECHNICAL PROPOSAL ENHANCEMENTS

Make these quick wins:

1. **Section 4 (Software Stack)** — "CMS (Latest Version)" is a placeholder.
   Name Umbraco explicitly with the version number.

2. **.NET 8 + Umbraco + Azure stack** — good for K-12 buyer.
   Verify M-DCPS's current stack. If different, propose migration. If already on Umbraco, lead with continuity.

3. **ADA "AA" compliance** — call out WCAG 2.1 AA explicitly (or 2.2 if claiming current).
   "ADA AA" alone is informal language for procurement reviewers.

4. **Section 8 (Project Team)** — every named team member must be a REAL, COMMITTABLE resource.
   The team is heavy on India-based titles — make US-based account/program management presence UNAMBIGUOUS.
   K-12 buyers care about timezone overlap and onsite availability.

5. **Cybersecurity & student data privacy** — add subsection covering:
   - FERPA compliance
   - COPPA compliance  
   - SOC 2 commitments
   For K-12 site handling student-adjacent data, this is a gap.

6. **References** — public-sector or K-12 references beat commercial references.

## CONE OF SILENCE
From issuance through Board agenda publication: ZERO contact with any Board member,
Superintendent, deputy supt, their staff, or evaluation committee.
ALL questions go through designated Procurement contact in writing only.
Violation = disqualification and ban from future bids.

## CRITICAL FLAGS

1. **Due date** — verify you're generating to the CURRENT ITB version, not September 2024 one.
   Procurement language gets revised between cycles.

2. **Ikomet (India) subcontractor** — biggest political/compliance vulnerability.
   Be ready to explain: data residency (US-only), access controls, no PII leaving US, US citizen project leadership.

3. **"At any cost"** — keep it inside the lines. The fastest way to lose permanently is
   misrepresentation on a sworn attachment. Bid forms are signed under penalty of perjury.
"""


def check_compliance(state, bid_id: str, documents: list[str]) -> str:
    """Tool: Run compliance audit on bid documents."""
    log.info("[bid_executor] compliance check: %s", bid_id)
    return json.dumps({
        "status": "pending_review",
        "bid_id": bid_id,
        "documents_submitted": documents,
        "critical_fail_points": [
            "Attachment 1 - subcontractor consistency",
            "Attachment 11 - reference validity (First Republic Bank)",
            "Attachment 18 - foreign subcontractor disclosure",
            "FL foreign corp registration status"
        ],
        "timestamp": datetime.now().isoformat()
    })


def enhance_technical_proposal(state, section: str, updates: dict) -> str:
    """Tool: Apply enhancement to technical proposal section."""
    log.info("[bid_executor] enhancing section: %s", section)
    return json.dumps({
        "section": section,
        "enhancement_applied": updates,
        "status": "enhanced"
    })


def verify_responsiveness(state, bid_id: str) -> str:
    """Tool: Final responsiveness verification before submission."""
    log.info("[bid_executor] verifying responsiveness: %s", bid_id)
    return json.dumps({
        "bid_id": bid_id,
        "responsiveness_verified": False,
        "checks_passed": [],
        "checks_failed": [],
        "recommendation": "REVIEW_REQUIRED"
    })


class BidExecutorAgent(BaseAgent):
    name = "bid_executor"
    description = "Orchestrates end-to-end bid response for a specific solicitation."
    max_iterations = 20
    max_tokens = 6000

    system_prompt = BID_PLAYBOOK

    def __init__(self, client: anthropic.Anthropic, state):
        tools = [
            Tool(
                name="check_compliance",
                description="Run compliance audit on bid documents, checking fail-points",
                input_schema={
                    "type": "object",
                    "required": ["bid_id", "documents"],
                    "properties": {
                        "bid_id": {"type": "string", "description": "The solicitation ID (e.g., ITB-23-014-JW)"},
                        "documents": {"type": "array", "items": {"type": "string"}, "description": "List of document paths to audit"},
                    },
                },
                fn=check_compliance,
            ),
            Tool(
                name="enhance_technical_proposal",
                description="Apply enhancement to a specific technical proposal section",
                input_schema={
                    "type": "object",
                    "required": ["section", "updates"],
                    "properties": {
                        "section": {"type": "string", "description": "Section name (e.g., 'Software Stack', 'Project Team')"},
                        "updates": {"type": "object", "description": "Enhancement updates to apply"},
                    },
                },
                fn=enhance_technical_proposal,
            ),
            Tool(
                name="verify_responsiveness",
                description="Final verification that bid meets responsiveness criteria",
                input_schema={
                    "type": "object",
                    "required": ["bid_id"],
                    "properties": {
                        "bid_id": {"type": "string", "description": "The solicitation ID"},
                    },
                },
                fn=verify_responsiveness,
            ),
        ]
        super().__init__(client, state, tools=tools)