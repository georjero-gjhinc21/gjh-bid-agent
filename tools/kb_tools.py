"""Knowledge / state tools available to specialist agents."""
from __future__ import annotations
from agents.base import Tool


def _list_recent_opportunities(state, hours: int = 26) -> list[dict]:
    return state.opportunities_for_digest(since_hours=hours)


def _list_compliance(state) -> list[dict]:
    return state.list_compliance()


def _list_contacts(state) -> list[dict]:
    return state.list_contacts()


list_recent_opportunities = Tool(
    name="list_recent_opportunities",
    description="List opportunities discovered in the last N hours, ordered by fit_score desc.",
    input_schema={
        "type": "object",
        "properties": {"hours": {"type": "integer", "description": "Default 26."}},
    },
    fn=_list_recent_opportunities,
)

list_compliance = Tool(
    name="list_compliance",
    description="List all tracked compliance items (COIs, licenses, recurring filings).",
    input_schema={"type": "object", "properties": {}},
    fn=_list_compliance,
)

list_contacts = Tool(
    name="list_contacts",
    description="List the contacts CRM (name, org, email, role, follow-ups).",
    input_schema={"type": "object", "properties": {}},
    fn=_list_contacts,
)
