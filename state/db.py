"""Thin SQLite wrapper. All agents share one instance via the orchestrator."""
from __future__ import annotations
import sqlite3
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class State:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        schema = Path(__file__).parent / "schema.sql"
        self.conn.executescript(schema.read_text())
        self.conn.commit()

    # ---------- opportunities ----------
    @staticmethod
    def opp_id(source: str, ref: str) -> str:
        return hashlib.sha1(f"{source}|{ref}".encode()).hexdigest()[:16]

    def opportunity_exists(self, opp_id: str) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM opportunities WHERE id = ?", (opp_id,)
        )
        return cur.fetchone() is not None

    def upsert_opportunity(self, opp: dict[str, Any]) -> str:
        opp.setdefault("id", self.opp_id(opp["source"], opp["source_detail"] or opp["title"]))
        opp.setdefault("discovered_at", _now())
        opp.setdefault("status", "new")
        cols = ",".join(opp.keys())
        placeholders = ",".join("?" for _ in opp)
        updates = ",".join(f"{k}=excluded.{k}" for k in opp.keys() if k != "id")
        self.conn.execute(
            f"INSERT INTO opportunities ({cols}) VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {updates}",
            tuple(opp.values()),
        )
        self.conn.commit()
        return opp["id"]

    def opportunities_for_digest(self, since_hours: int = 26) -> list[dict]:
        cur = self.conn.execute(
            "SELECT * FROM opportunities WHERE discovered_at > datetime('now', ?) "
            "ORDER BY fit_score DESC, discovered_at DESC",
            (f"-{since_hours} hours",),
        )
        return [dict(r) for r in cur.fetchall()]

    # ---------- analyses / strategies ----------
    def upsert_analysis(self, opp_id: str, data: dict):
        data = {**data, "opp_id": opp_id, "analyzed_at": _now()}
        for key in ("requirements", "mandatory_forms", "risks"):
            if isinstance(data.get(key), list):
                data[key] = json.dumps(data[key])
        cols = ",".join(data.keys())
        ph = ",".join("?" for _ in data)
        upd = ",".join(f"{k}=excluded.{k}" for k in data if k != "opp_id")
        self.conn.execute(
            f"INSERT INTO analyses ({cols}) VALUES ({ph}) "
            f"ON CONFLICT(opp_id) DO UPDATE SET {upd}",
            tuple(data.values()),
        )
        self.conn.commit()

    def upsert_strategy(self, opp_id: str, data: dict):
        data = {**data, "opp_id": opp_id, "created_at": _now()}
        cols = ",".join(data.keys())
        ph = ",".join("?" for _ in data)
        upd = ",".join(f"{k}=excluded.{k}" for k in data if k != "opp_id")
        self.conn.execute(
            f"INSERT INTO strategies ({cols}) VALUES ({ph}) "
            f"ON CONFLICT(opp_id) DO UPDATE SET {upd}",
            tuple(data.values()),
        )
        self.conn.commit()

    # ---------- compliance ----------
    def seed_compliance(self, items: list[dict]):
        for it in items:
            cur = self.conn.execute(
                "SELECT 1 FROM compliance_items WHERE name = ?", (it["name"],)
            )
            if cur.fetchone():
                continue
            self.conn.execute(
                "INSERT INTO compliance_items (name, renews, owner, notes) "
                "VALUES (?,?,?,?)",
                (it["name"], it.get("renews"), it.get("owner"), it.get("notes")),
            )
        self.conn.commit()

    def list_compliance(self) -> list[dict]:
        cur = self.conn.execute("SELECT * FROM compliance_items")
        return [dict(r) for r in cur.fetchall()]

    # ---------- contacts ----------
    def seed_contacts(self, contacts: list[dict]):
        for c in contacts:
            cur = self.conn.execute(
                "SELECT 1 FROM contacts WHERE email = ? OR (name = ? AND org = ?)",
                (c.get("email", ""), c["name"], c.get("org", "")),
            )
            if cur.fetchone():
                continue
            self.conn.execute(
                "INSERT INTO contacts (name, org, email, phone, role) "
                "VALUES (?,?,?,?,?)",
                (c["name"], c.get("org"), c.get("email"), c.get("phone"), c.get("role")),
            )
        self.conn.commit()

    def list_contacts(self) -> list[dict]:
        cur = self.conn.execute("SELECT * FROM contacts")
        return [dict(r) for r in cur.fetchall()]

    # ---------- agent runs ----------
    def log_run(self, agent: str, status: str, summary: str = "", error: str = ""):
        self.conn.execute(
            "INSERT INTO agent_runs (agent, started_at, ended_at, status, summary, error) "
            "VALUES (?,?,?,?,?,?)",
            (agent, _now(), _now(), status, summary, error),
        )
        self.conn.commit()

    def log_digest(self, body: str):
        self.conn.execute(
            "INSERT INTO digests (sent_at, body) VALUES (?, ?)", (_now(), body)
        )
        self.conn.commit()
