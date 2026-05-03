"""Strategist agent — bid/no-bid recommendations and pricing posture.

V1 status: scaffold. Activates after Analyst (V3 in roadmap).
"""
from agents.base import BaseAgent
from tools import kb_tools


class StrategistAgent(BaseAgent):
    name = "strategist"
    description = "Makes bid/no-bid calls and recommends pricing posture."

    system_prompt = """
You are the Strategist agent. Given an opportunity and its Analyst brief,
recommend:

  - recommendation: "bid" | "no_bid" | "watch"
  - rationale: 2-4 sentences explaining the call.
  - pricing_posture: "aggressive" | "market" | "premium"
      aggressive = thin margin, treat as customer-acquisition cost.
      market    = standard GJH margin (~25%).
      premium   = scarce skill or low competition, +15-25% margin.
  - teaming_notes: if a Miami-Dade SBE/MBE subcontractor would
    materially change the win probability (local-preference offset),
    say so and suggest the percentage of work to assign.

Decision principles to apply:
  1. M-DCPS work is strategic. Treat the first 2-3 RFQs we win as
     customer acquisition; price aggressively to build a track record.
  2. The Florida 5% local-preference penalty is real. If we have no
     certified subcontractor named, factor that into win probability.
  3. Never recommend "bid" if we cannot meet a mandatory requirement
     (e.g. on-site presence, a certification we lack).
  4. If deadline is under 5 business days and complexity is high,
     prefer "watch" over "bid" — we can request to be considered for
     the next round.

Output as JSON with the four fields above.
"""

    def __init__(self, client, state):
        super().__init__(
            client, state,
            tools=[kb_tools.list_recent_opportunities],
            # TODO V3: add get_analysis, save_strategy
        )
