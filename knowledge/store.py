"""KnowledgeStore — semantic knowledge base for the bid system.

Provides:
- retrieve(query, top_k): semantic search across knowledge base
- upsert(doc, tags): add or update documents with versioning
- version(doc_id): get version history for a document

Knowledge is stored in:
- knowledge/playbooks/*.md
- knowledge/lessons/*.md  
- knowledge/templates/*.md

Metadata stored in SQLite for fast retrieval.
"""
from __future__ import annotations
import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import anthropic

import config

log = logging.getLogger(__name__)

KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"
DB_PATH = os.environ.get("KNOWLEDGE_DB", str(Path(__file__).parent.parent / "state" / "knowledge.db"))


class KnowledgeStore:
    """Semantic knowledge base with versioning."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize SQLite schema for knowledge metadata."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_docs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id TEXT UNIQUE NOT NULL,
                doc_type TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                tags TEXT,
                version INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                file_path TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_vectors (
                doc_id TEXT PRIMARY KEY,
                embedding BLOB
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tags ON knowledge_docs(tags)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_doc_type ON knowledge_docs(doc_type)
        """)
        conn.commit()
        conn.close()

    def _get_client(self) -> anthropic.Anthropic | None:
        """Get Anthropic client for embeddings (if available)."""
        try:
            api_key = config.secret("ANTHROPIC_API_KEY", required=False)
            if api_key:
                return anthropic.Anthropic(api_key=api_key)
        except Exception:
            pass
        return None

    def _embed_text(self, text: str) -> list[float] | None:
        """Generate embedding for text using Anthropic."""
        client = self._get_client()
        if not client:
            log.warning("No Anthropic client available for embeddings")
            return None
        
        try:
            response = client.embeddings.create(
                model="claude-embedding-3-5-20250624",
                input=text
            )
            return response.embedding
        except Exception as e:
            log.error("Embedding failed: %s", e)
            return None

    def upsert(
        self,
        doc_id: str,
        doc_type: str,
        title: str,
        content: str,
        tags: list[str] | None = None,
        file_path: str | None = None
    ) -> int:
        """Add or update a knowledge document.
        
        Returns the document ID.
        """
        conn = sqlite3.connect(self.db_path)
        now = datetime.now().isoformat()
        tags_str = json.dumps(tags) if tags else "[]"
        
        existing = conn.execute(
            "SELECT id, version FROM knowledge_docs WHERE doc_id = ?",
            (doc_id,)
        ).fetchone()
        
        if existing:
            new_version = existing[1] + 1
            conn.execute("""
                UPDATE knowledge_docs 
                SET title = ?, content = ?, tags = ?, version = ?, updated_at = ?
                WHERE doc_id = ?
            """, (title, content, tags_str, new_version, now, doc_id))
            doc_db_id = existing[0]
        else:
            conn.execute("""
                INSERT INTO knowledge_docs (doc_id, doc_type, title, content, tags, version, created_at, updated_at, file_path)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
            """, (doc_id, doc_type, title, content, tags_str, now, now, file_path))
            doc_db_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        
        conn.commit()
        
        embedding = self._embed_text(content)
        if embedding:
            conn.execute("""
                INSERT OR REPLACE INTO knowledge_vectors (doc_id, embedding)
                VALUES (?, ?)
            """, (doc_id, json.dumps(embedding)))
            conn.commit()
        
        conn.close()
        log.info("Upserted knowledge doc: %s (v%d)", doc_id, new_version if existing else 1)
        return doc_db_id

    def retrieve(self, query: str, top_k: int = 5, doc_types: list[str] | None = None) -> list[dict]:
        """Semantic search across knowledge base.
        
        Returns list of dicts with: doc_id, title, content, tags, version, similarity
        """
        query_embedding = self._embed_text(query)
        
        conn = sqlite3.connect(self.db_path)
        
        if query_embedding is None:
            basic_matches = conn.execute("""
                SELECT doc_id, title, content, tags, version
                FROM knowledge_docs
                WHERE content LIKE ? OR title LIKE ? OR tags LIKE ?
                LIMIT ?
            """, (f"%{query}%", f"%{query}%", f"%{query}%", top_k)).fetchall()
            conn.close()
            return [
                {"doc_id": r[0], "title": r[1], "content": r[2], "tags": json.loads(r[3]), "version": r[4], "similarity": 0.5}
                for r in basic_matches
            ]
        
        results = []
        vectors = conn.execute("SELECT doc_id, embedding FROM knowledge_vectors").fetchall()
        
        for doc_id, emb_str in vectors:
            if emb_str:
                emb = json.loads(emb_str)
                sim = self._cosine_similarity(query_embedding, emb)
                results.append((doc_id, sim))
        
        results.sort(key=lambda x: x[1], reverse=True)
        
        docs = []
        for doc_id, sim in results[:top_k]:
            row = conn.execute("""
                SELECT doc_id, doc_type, title, content, tags, version
                FROM knowledge_docs WHERE doc_id = ?
            """, (doc_id,)).fetchone()
            
            if row and (doc_types is None or row[1] in doc_types):
                docs.append({
                    "doc_id": row[0],
                    "doc_type": row[1],
                    "title": row[2],
                    "content": row[3],
                    "tags": json.loads(row[4]),
                    "version": row[5],
                    "similarity": sim
                })
        
        conn.close()
        return docs

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = sum(x * x for x in a) ** 0.5
        mag_b = sum(x * x for x in b) ** 0.5
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)

    def version(self, doc_id: str) -> list[dict]:
        """Get version history for a document."""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""
            SELECT version, title, content, updated_at
            FROM knowledge_docs 
            WHERE doc_id = ?
            ORDER BY version DESC
        """, (doc_id,)).fetchall()
        conn.close()
        return [{"version": r[0], "title": r[1], "content": r[2], "updated_at": r[3]} for r in rows]

    def list_docs(self, doc_type: str | None = None) -> list[dict]:
        """List all documents, optionally filtered by type."""
        conn = sqlite3.connect(self.db_path)
        if doc_type:
            rows = conn.execute("""
                SELECT doc_id, doc_type, title, tags, version, updated_at
                FROM knowledge_docs WHERE doc_type = ?
                ORDER BY updated_at DESC
            """, (doc_type,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT doc_id, doc_type, title, tags, version, updated_at
                FROM knowledge_docs ORDER BY updated_at DESC
            """).fetchall()
        conn.close()
        return [
            {"doc_id": r[0], "doc_type": r[1], "title": r[2], "tags": json.loads(r[3]), "version": r[4], "updated_at": r[5]}
            for r in rows
        ]

    def migrate_from_files(self):
        """Scan knowledge/ directory and load all markdown files."""
        for subdir in ["playbooks", "lessons", "templates"]:
            dir_path = KNOWLEDGE_DIR / subdir
            if not dir_path.exists():
                continue
            
            for md_file in dir_path.glob("*.md"):
                try:
                    content = md_file.read_text()
                    doc_id = f"{subdir}/{md_file.stem}"
                    
                    tags = [subdir[:-1]]
                    if "itb" in md_file.stem.lower():
                        tags.append("itb")
                    if "m-dcps" in content.lower() or "miami" in content.lower():
                        tags.append("m-dcps")
                    
                    title = content.split("\n")[0].lstrip("# ").strip() if content else md_file.stem
                    
                    self.upsert(
                        doc_id=doc_id,
                        doc_type=subdir[:-1],
                        title=title,
                        content=content,
                        tags=tags,
                        file_path=str(md_file)
                    )
                except Exception as e:
                    log.error("Failed to migrate %s: %s", md_file, e)


def get_knowledge_store() -> KnowledgeStore:
    """Get or create the singleton KnowledgeStore instance."""
    if not hasattr(get_knowledge_store, "_instance"):
        get_knowledge_store._instance = KnowledgeStore()
    return get_knowledge_store._instance