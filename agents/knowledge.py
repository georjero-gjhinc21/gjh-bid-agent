"""Knowledge agent — curates and serves GJH's institutional memory.

V1 status: scaffold. Currently delegates to SQLite via kb_tools. The
intended V2+ design is a vector store over:
  - Past bid responses
  - Signed forms and certifications
  - Team bios and resumes
  - Reference projects and case studies
  - Email threads with procurement officers

Other agents call this one when they need "what have we said before about
X" or "what's our standard answer to Y."
"""
from agents.base import BaseAgent
from tools import kb_tools


class KnowledgeAgent(BaseAgent):
    name = "knowledge"
    description = "Serves institutional memory: past bids, forms, references, team bios."

    system_prompt = """
You are the Knowledge agent. Other agents query you for firm history.

Today you have only the structured tables (opportunities, contacts,
compliance). When asked something you can't answer from those, say so
honestly and recommend what artifact should be added to the KB.

When the KB is expanded with the past-bid corpus and team archive,
you'll route queries through retrieval and return short, source-cited
answers.
"""

    def __init__(self, client, state):
        super().__init__(
            client, state,
            tools=[
                kb_tools.list_recent_opportunities,
                kb_tools.list_contacts,
                kb_tools.list_compliance,
                # TODO V2+: vector_search, list_past_bids, get_team_bio
            ],
        )
