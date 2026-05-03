"""Telemetry + Guardrails + HITL Approval.

- Every LLM call logged with: prompt, response, tokens, cost, latency, agent_id
- Cost ceiling per run (default $25), hard stop if exceeded
- Escalation triggers: submit bid, sign document, contact external, spend >$X
- HITL approval required for sensitive actions
- Cone of Silence enforcement: refuse to contact board members during active solicitation
"""
from __future__ import annotations
import json
import logging
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

TELEMETRY_DB = os.environ.get("TELEMETRY_DB", str(Path(__file__).parent / "state" / "telemetry.db"))
COST_CEILING = float(os.environ.get("COST_CEILING", "25.0"))
HITL_THRESHOLD = float(os.environ.get("HITL_THRESHOLD", "100.0"))

CONE_OF_SILENCE_PATTERNS = [
    "board member", "superintendent", "deputy superintendent",
    "evaluation committee", "school board", "board chair"
]

CONE_OF_SILENCE_EXPIRY_DAYS = 30


class Telemetry:
    """Log LLM calls and enforce guardrails."""

    def __init__(self, db_path: str = TELEMETRY_DB):
        self.db_path = db_path
        self.run_cost = 0.0
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS llm_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                model TEXT,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                total_tokens INTEGER,
                cost_usd REAL,
                latency_ms INTEGER,
                prompt_preview TEXT,
                status TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS approvals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                requested_at TEXT NOT NULL,
                approved_at TEXT,
                approved_by TEXT,
                status TEXT
            )
        """)
        conn.commit()
        conn.close()

    def log_call(self, run_id: str, agent_id: str, model: str, prompt_tokens: int, 
                 completion_tokens: int, latency_ms: int, prompt_preview: str, 
                 status: str = "ok"):
        """Log an LLM call."""
        total_tokens = prompt_tokens + completion_tokens
        cost = self._calculate_cost(model, total_tokens)
        
        self.run_cost += cost
        
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO llm_calls (run_id, agent_id, timestamp, model, prompt_tokens, completion_tokens, total_tokens, cost_usd, latency_ms, prompt_preview, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (run_id, agent_id, datetime.now().isoformat(), model, prompt_tokens, completion_tokens, total_tokens, cost, latency_ms, prompt_preview[:500], status))
        conn.commit()
        conn.close()
        
        log.info("[telemetry] LLM call: %s %s cost=$%.4f total=$%.2f", agent_id, model, cost, self.run_cost)
        
        if self.run_cost > COST_CEILING:
            log.error("[telemetry] COST CEILING EXCEEDED: $%.2f > $%.2f", self.run_cost, COST_CEILING)
            raise RuntimeError(f"Cost ceiling exceeded: ${self.run_cost:.2f} > ${COST_CEILING}")

    @staticmethod
    def _calculate_cost(model: str, tokens: int) -> float:
        """Calculate cost based on model pricing (approximate)."""
        rates = {
            "opus": 15.0 / 1_000_000,
            "sonnet": 3.0 / 1_000_000,
            "haiku": 0.2 / 1_000_000,
        }
        for prefix, rate in rates.items():
            if prefix in model.lower():
                return tokens * rate
        return tokens * 1.0 / 1_000_000

    def request_approval(self, run_id: str, action: str, details: dict) -> dict:
        """Request HITL approval for a sensitive action."""
        conn = sqlite3.connect(self.db_path)
        
        conn.execute("""
            INSERT INTO approvals (run_id, action, details, requested_at, status)
            VALUES (?, ?, ?, ?, 'PENDING')
        """, (run_id, action, json.dumps(details), datetime.now().isoformat()))
        conn.commit()
        approval_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        
        log.warning("[telemetry] HITL approval requested: %s %s", action, details)
        
        return {
            "approval_id": approval_id,
            "status": "PENDING",
            "action": action,
            "details": details,
            "message": "Human approval required before proceeding"
        }

    def check_cone_of_silence(self, recipient: str, solicitation_id: str = "") -> bool:
        """Check if recipient is protected by Cone of Silence."""
        recipient_lower = recipient.lower()
        
        for pattern in CONE_OF_SILENCE_PATTERNS:
            if pattern in recipient_lower:
                log.warning("[telemetry] Cone of Silence violation: %s matches '%s'", recipient, pattern)
                return True
        
        return False

    def enforce_approval_gate(self, action: str, details: dict, required: bool = True) -> bool:
        """Check if approval is needed and if it's granted."""
        approval_needed = (
            "submit" in action.lower() or
            "sign" in action.lower() or 
            "send" in action.lower() or
            details.get("estimated_cost", 0) > HITL_THRESHOLD
        )
        
        if not approval_needed:
            return True
        
        if details.get("recipient"):
            if self.check_cone_of_silence(details["recipient"], details.get("solicitation_id", "")):
                log.error("[telemetry] BLOCKED: Cone of Silence violation")
                return False
        
        return not required


_telemetry: Telemetry | None = None


def get_telemetry() -> Telemetry:
    """Get singleton Telemetry."""
    global _telemetry
    if _telemetry is None:
        _telemetry = Telemetry()
    return _telemetry