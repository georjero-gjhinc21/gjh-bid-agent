"""Memory module — three-tier persistent memory for the bid system.

Three tiers:
a) episodic: every action, observation, decision (JSONL log per run)
b) semantic: extracted facts (vendor X requires Y, attachment Z deadline is W)
c) procedural: refined prompts and workflow templates that worked

Each agent reads relevant memory at start, writes new memory at end.
"""
from __future__ import annotations
import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

MEMORY_DIR = Path(__file__).parent / "memory"
DB_PATH = os.environ.get("MEMORY_DB", str(Path(__file__).parent / "state" / "memory.db"))


class MemoryStore:
    """Three-tier memory system."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        MEMORY_DIR.mkdir(exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize SQLite for semantic and procedural memory."""
        conn = sqlite3.connect(self.db_path)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS semantic_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fact_key TEXT NOT NULL,
                fact_value TEXT NOT NULL,
                source_run TEXT,
                created_at TEXT NOT NULL,
                expires_at TEXT
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS procedural_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_type TEXT NOT NULL,
                name TEXT NOT NULL,
                content TEXT NOT NULL,
                context TEXT,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                last_used TEXT,
                created_at TEXT NOT NULL
            )
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_fact_key ON semantic_facts(fact_key)
        """)
        
        conn.commit()
        conn.close()

    def log_episodic(self, event_type: str, content: dict, tags: list[str] | None = None):
        """Log an episodic event to JSONL."""
        episodic_file = MEMORY_DIR / f"episodic_{self.run_id}.jsonl"
        
        event = {
            "run_id": self.run_id,
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "content": content,
            "tags": tags or []
        }
        
        with open(episodic_file, "a") as f:
            f.write(json.dumps(event) + "\n")
        
        log.info("[memory] logged episodic: %s", event_type)

    def store_fact(self, key: str, value: str, source_run: str | None = None, expires_days: int | None = None):
        """Store a semantic fact."""
        conn = sqlite3.connect(self.db_path)
        now = datetime.now().isoformat()
        
        expires_at = None
        if expires_days:
            from datetime import timedelta
            expires_at = (datetime.now() + timedelta(days=expires_days)).isoformat()
        
        conn.execute("""
            INSERT INTO semantic_facts (fact_key, fact_value, source_run, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
        """, (key, value, source_run or self.run_id, now, expires_at))
        
        conn.commit()
        conn.close()
        log.info("[memory] stored fact: %s", key)

    def get_fact(self, key: str) -> str | None:
        """Retrieve a semantic fact."""
        conn = sqlite3.connect(self.db_path)
        row = conn.execute("""
            SELECT fact_value FROM semantic_facts
            WHERE fact_key = ? AND (expires_at IS NULL OR expires_at > ?)
            ORDER BY created_at DESC LIMIT 1
        """, (key, datetime.now().isoformat())).fetchone()
        conn.close()
        return row[0] if row else None

    def query_facts(self, key_pattern: str) -> list[dict]:
        """Query facts by key pattern."""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""
            SELECT fact_key, fact_value, source_run, created_at
            FROM semantic_facts
            WHERE fact_key LIKE ? AND (expires_at IS NULL OR expires_at > ?)
            ORDER BY created_at DESC
        """, (f"%{key_pattern}%", datetime.now().isoformat())).fetchall()
        conn.close()
        return [{"key": r[0], "value": r[1], "source": r[2], "created": r[3]} for r in rows]

    def store_procedural(self, memory_type: str, name: str, content: str, context: dict | None = None):
        """Store procedural memory (refined prompts, templates that worked)."""
        conn = sqlite3.connect(self.db_path)
        now = datetime.now().isoformat()
        
        existing = conn.execute("""
            SELECT id FROM procedural_memory
            WHERE memory_type = ? AND name = ?
        """, (memory_type, name)).fetchone()
        
        if existing:
            conn.execute("""
                UPDATE procedural_memory
                SET content = ?, context = ?, last_used = ?
                WHERE id = ?
            """, (content, json.dumps(context) if context else None, now, existing[0]))
        else:
            conn.execute("""
                INSERT INTO procedural_memory (memory_type, name, content, context, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (memory_type, name, content, json.dumps(context) if context else None, now))
        
        conn.commit()
        conn.close()
        log.info("[memory] stored procedural: %s/%s", memory_type, name)

    def get_procedural(self, memory_type: str, name: str) -> dict | None:
        """Retrieve procedural memory."""
        conn = sqlite3.connect(self.db_path)
        row = conn.execute("""
            SELECT content, context, success_count, failure_count, last_used
            FROM procedural_memory
            WHERE memory_type = ? AND name = ?
        """, (memory_type, name)).fetchone()
        conn.close()
        
        if row:
            return {
                "content": row[0],
                "context": json.loads(row[1]) if row[1] else None,
                "success_count": row[2],
                "failure_count": row[3],
                "last_used": row[4]
            }
        return None

    def list_procedural(self, memory_type: str | None = None) -> list[dict]:
        """List procedural memories."""
        conn = sqlite3.connect(self.db_path)
        if memory_type:
            rows = conn.execute("""
                SELECT memory_type, name, success_count, failure_count, last_used
                FROM procedural_memory
                WHERE memory_type = ?
                ORDER BY success_count DESC
            """, (memory_type,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT memory_type, name, success_count, failure_count, last_used
                FROM procedural_memory
                ORDER BY success_count DESC
            """).fetchall()
        conn.close()
        return [{"type": r[0], "name": r[1], "success": r[2], "failures": r[3], "last_used": r[4]} for r in rows]

    def record_outcome(self, memory_type: str, name: str, success: bool):
        """Record success/failure for a procedural memory."""
        conn = sqlite3.connect(self.db_path)
        if success:
            conn.execute("""
                UPDATE procedural_memory SET success_count = success_count + 1, last_used = ?
                WHERE memory_type = ? AND name = ?
            """, (datetime.now().isoformat(), memory_type, name))
        else:
            conn.execute("""
                UPDATE procedural_memory SET failure_count = failure_count + 1, last_used = ?
                WHERE memory_type = ? AND name = ?
            """, (datetime.now().isoformat(), memory_type, name))
        conn.commit()
        conn.close()

    def get_episodic_log(self, run_id: str | None = None) -> list[dict]:
        """Get episodic log for a specific run."""
        if run_id:
            files = [f for f in MEMORY_DIR.glob(f"episodic_{run_id}.jsonl")]
        else:
            files = list(MEMORY_DIR.glob("episodic_*.jsonl"))
        
        events = []
        for f in files:
            for line in f.read_text().strip().split("\n"):
                if line:
                    events.append(json.loads(line))
        return events

    def query_by_tags(self, tags: list[str]) -> list[dict]:
        """Query episodic memory by tags."""
        matching = []
        for f in MEMORY_DIR.glob("episodic_*.jsonl"):
            for line in f.read_text().strip().split("\n"):
                if line:
                    event = json.loads(line)
                    if any(t in event.get("tags", []) for t in tags):
                        matching.append(event)
        return matching


_memory_store: MemoryStore | None = None


def get_memory_store() -> MemoryStore:
    """Get or create singleton MemoryStore."""
    global _memory_store
    if _memory_store is None:
        _memory_store = MemoryStore()
    return _memory_store