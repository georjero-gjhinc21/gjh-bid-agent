"""Central configuration for the GJH bid-agent framework.

Everything firm-specific lives here. Agents read from this — no other
module hard-codes firm details.
"""
from __future__ import annotations
import os
from pathlib import Path

# ---------- runtime ----------
ROOT = Path(__file__).resolve().parent
DB_PATH = os.environ.get("DB_PATH", str(ROOT / "state" / "bids.db"))
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOOKBACK_HOURS = int(os.environ.get("LOOKBACK_HOURS", "26"))

# ---------- secrets (read at runtime) ----------
def secret(name: str, required: bool = True) -> str:
    val = os.environ.get(name, "")
    if required and not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val

# ---------- model selection per agent ----------
# Cheaper agents use Haiku; planning/reasoning uses Sonnet; deep document
# work uses Opus. Override per-agent via env if needed.
MODELS = {
    "orchestrator": os.environ.get("MODEL_ORCHESTRATOR", "claude-sonnet-4-6"),
    "scout":        os.environ.get("MODEL_SCOUT",        "claude-haiku-4-5-20251001"),
    "analyst":      os.environ.get("MODEL_ANALYST",      "claude-opus-4-7"),
    "strategist":   os.environ.get("MODEL_STRATEGIST",   "claude-opus-4-7"),
    "compliance":   os.environ.get("MODEL_COMPLIANCE",   "claude-haiku-4-5-20251001"),
    "drafter":      os.environ.get("MODEL_DRAFTER",      "claude-sonnet-4-6"),
    "relationship": os.environ.get("MODEL_RELATIONSHIP", "claude-sonnet-4-6"),
    "knowledge":    os.environ.get("MODEL_KNOWLEDGE",    "claude-haiku-4-5-20251001"),
}

# ---------- firm profile ----------
# Used by every agent to understand who we are and what we want.
FIRM_PROFILE = """
GJH INC is a California S-corp (FEIN 27-0254840), headquartered at
697 Auburn Drive, Vallejo CA 94589. CEO George Vincent. Stack: .NET 8,
Umbraco CMS, Azure App Service, Azure SQL, jQuery/HTML/CSS frontends.

Active awards:
  - Miami-Dade County Public Schools (M-DCPS), ITB-23-014-JW Website
    Development, awarded 2024, term 3 years + 2x1-year renewals.
    Vendor reference: MDCPS-R2992. Awarded as pre-approved vendor in a
    non-exclusive pool; real work flows through RFQs over $1,000 awarded
    to lowest responsive responsible bidder.

Insurance on file:
  - Hiscox Cyber & Data Risk: P104.580.719.2, expires 2027-04-05
  - Hiscox General Liability: P104.580.718.2, expires 2027-04-05

Known weaknesses to compensate for:
  - Out-of-state (CA), so subject to FL 5% local-preference penalty
    under Florida Statute 287.084 and MDCPS Policy 6320.05.
  - No Florida foreign-corp registration on file (Sunbiz status unknown).
  - Reference depth thin (one recent reference: Method Hub, ~$150K).

Strategy posture:
  - Treat first 2-3 RFQs as customer acquisition, bid aggressively.
  - Pursue Miami-Dade SBE/MBE-certified subcontractor partnerships to
    neutralize local-preference penalty.
  - File monthly OEO compliance reports; missing one drops us from pool.
"""

# ---------- targeting ----------
# What the Scout looks for, expressed for Claude to reason on.
TARGETING = """
Priority order:
  1. Anything from Miami-Dade County Public Schools (M-DCPS) procurement
     — including new ITBs, RFQs against ITB-23-014-JW, addenda, and
     compliance notices.
  2. Florida K-12 / district / county / municipal solicitations for
     website, web app, CMS, .NET, or Azure work.
  3. US public-sector website / CMS / web app solicitations under ~$500K.

Ignore:
  - Construction, food, transport, janitorial, supplies, uniforms.
  - Non-IT professional services (legal, audit, marketing, HR).
  - Anything outside the US.
  - RFPs requiring on-site presence we cannot reasonably provide.
"""

# ---------- sources ----------
# Senders whose alerts the Scout reads from Gmail. Add as discovered.
ALERT_SENDERS = [
    "notify@periscopeholdings.com",            # S2G / Periscope
    "noreply@mybidmatch.com",                  # mybidmatch / Onvia
    "alerts-noreply@mg.instantmarkets.com",    # InstantMarkets
    "notices@publicpurchase.com",              # PublicPurchase
    "noreply@demandstar.com",                  # DemandStar (MDCPS uses this)
    "alerts@bidnetdirect.com",                 # BidNet Direct
    "noreply@bonfirehub.com",                  # Bonfire
]

# Direct sources to scrape. Keep small at first.
WEB_SOURCES = [
    {
        "name": "M-DCPS Procurement",
        "url": "http://procurement.dadeschools.net",
        "priority": 1,
    },
    {
        "name": "M-DCPS Active Solicitations",
        "url": "http://procurement.dadeschools.net/itbs.asp",
        "priority": 1,
    },
]

# ---------- compliance calendar ----------
# Static for V1; Compliance agent will mature this into a managed table.
COMPLIANCE_ITEMS = [
    {
        "name": "Hiscox Cyber liability COI",
        "renews": "2027-04-05",
        "owner": "George",
        "notes": "Auto-renewed; verify ACORD on file with MDCPS Risk Mgmt.",
    },
    {
        "name": "Hiscox General Liability COI",
        "renews": "2027-04-05",
        "owner": "George",
        "notes": "Auto-renewed; verify ACORD on file with MDCPS Risk Mgmt.",
    },
    {
        "name": "City of Vallejo business license",
        "renews": "2025-06-30",
        "owner": "George",
        "notes": "License #11716616. Renew via HdL.",
    },
    {
        "name": "California SOI annual filing",
        "renews": "2024-12-31",
        "owner": "George",
        "notes": "Statement of Information, CA Secretary of State.",
    },
    {
        "name": "MDCPS OEO monthly compliance report",
        "renews": "monthly",
        "owner": "George",
        "notes": "miamidadeschools.diversitycompliance.com — required while in pool.",
    },
    {
        "name": "Florida foreign corporation registration",
        "renews": "unknown",
        "owner": "George",
        "notes": "Verify on Sunbiz; file via FL DOS form CR2E007 if missing.",
    },
]

# ---------- contacts ----------
# Seed for the Relationship agent. Maintained in DB once that agent activates.
SEED_CONTACTS = [
    {
        "name": "Joseph Wenham",
        "org": "M-DCPS Procurement Management Services",
        "email": "jwenham@dadeschools.net",
        "phone": "(305) 995-2338",
        "role": "Purchasing Agent — ITB-23-014-JW",
    },
    {
        "name": "MDCPS Office of Economic Opportunity",
        "org": "M-DCPS",
        "email": "OEO@dadeschools.net",
        "phone": "(305) 995-1307",
        "role": "Certification & compliance reporting",
    },
    {
        "name": "MDCPS Vendor Compliance",
        "org": "M-DCPS",
        "email": "COI@dadeschools.net",
        "phone": "",
        "role": "COI submission and renewal",
    },
]
