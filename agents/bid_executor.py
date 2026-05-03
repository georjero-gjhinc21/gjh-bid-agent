"""BidExecutorAgent — orchestrates bid response for any solicitation.

Uses KnowledgeStore at runtime to retrieve relevant playbook, lessons, and templates.
No hardcoded bid-specific facts in code.
"""
from __future__ import annotations
import json
import logging
from datetime import datetime
from typing import Any

import anthropic

from agents.base import BaseAgent, Tool
from knowledge import get_knowledge_store
import config

log = logging.getLogger(__name__)

BASE_INSTRUCTIONS = """
You are the BidExecutor — an autonomous agent that orchestrates bid responses.

You do NOT have hardcoded knowledge about specific bids. Instead, you must:
1. Retrieve relevant playbooks from the knowledge base
2. Check for applicable lessons from past bids
3. Use templates for standard documents

Your role:
- Plan the bid response workflow
- Execute each step with quality
- Self-critique after each deliverable
- Log all decisions to memory

## CORE PRINCIPLES
- Never hardcode bid-specific facts — always retrieve from knowledge base
- Every deliverable is critique-able — run CriticAgent after completion
- Log to memory after each step for future learning
- Check Cone of Silence before any external communication

## AVAILABLE TOOLS
- retrieve_knowledge: Get relevant playbooks, lessons, templates
- check_compliance: Audit documents against requirements
- enhance_proposal: Improve technical sections
- verify_responsiveness: Final check before submission
- log_to_memory: Store decisions and learnings
"""


def retrieve_knowledge(state, query: str, top_k: int = 5) -> str:
    """Tool: Retrieve relevant knowledge from the knowledge base."""
    log.info("[bid_executor] retrieving knowledge: %s", query[:100])
    store = get_knowledge_store()
    results = store.retrieve(query, top_k=top_k)
    return json.dumps({
        "query": query,
        "results": [
            {
                "doc_id": r["doc_id"],
                "title": r["title"],
                "content": r["content"][:500] + "..." if len(r["content"]) > 500 else r["content"],
                "tags": r["tags"],
                "similarity": round(r["similarity"], 3)
            }
            for r in results
        ],
        "count": len(results)
    })


def check_compliance(state, bid_id: str, documents: list[str]) -> str:
    """Tool: Run compliance audit on bid documents."""
    log.info("[bid_executor] compliance check: %s", bid_id)
    return json.dumps({
        "status": "pending_review",
        "bid_id": bid_id,
        "documents_submitted": documents,
        "critical_fail_points": [
            "Verify all attachments present",
            "Check signatures and dates",
            "Validate reference currency"
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


def log_to_memory(state, event_type: str, content: str, tags: list[str] | None = None) -> str:
    """Tool: Log an event or decision to memory."""
    log.info("[bid_executor] logging to memory: %s", event_type)
    from knowledge import get_knowledge_store
    store = get_knowledge_store()
    doc_id = f"memory/{event_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    store.upsert(
        doc_id=doc_id,
        doc_type="memory",
        title=event_type,
        content=content,
        tags=tags or [event_type]
    )
    return json.dumps({"status": "logged", "doc_id": doc_id})


class BidExecutorAgent(BaseAgent):
    name = "bid_executor"
    description = "Orchestrates end-to-end bid response using knowledge base."
    max_iterations = 20
    max_tokens = 6000

    system_prompt = BASE_INSTRUCTIONS

    def __init__(self, client: anthropic.Anthropic, state):
        tools = [
            Tool(
                name="retrieve_knowledge",
                description="Retrieve relevant playbooks, lessons, or templates from knowledge base",
                input_schema={
                    "type": "object",
                    "required": ["query"],
                    "properties": {
                        "query": {"type": "string", "description": "Search query for knowledge base"},
                        "top_k": {"type": "integer", "description": "Number of results to return (default 5)", "default": 5},
                    },
                },
                fn=retrieve_knowledge,
            ),
            Tool(
                name="check_compliance",
                description="Run compliance audit on bid documents",
                input_schema={
                    "type": "object",
                    "required": ["bid_id", "documents"],
                    "properties": {
                        "bid_id": {"type": "string", "description": "The solicitation ID"},
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
                        "section": {"type": "string", "description": "Section name"},
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
            Tool(
                name="log_to_memory",
                description="Log a decision, event, or learning to memory",
                input_schema={
                    "type": "object",
                    "required": ["event_type", "content"],
                    "properties": {
                        "event_type": {"type": "string", "description": "Type of event (e.g., 'decision', 'observation', 'lesson')"},
                        "content": {"type": "string", "description": "What to log"},
                        "tags": {"type": "array", "items": {"type": "string"}, "description": "Optional tags"},
                    },
                },
                fn=log_to_memory,
            ),
        ]
        super().__init__(client, state, tools=tools)

    def build_input(self, task: str, context: dict | None = None) -> str:
        """Build input by retrieving relevant knowledge first."""
        store = get_knowledge_store()
        
        bid_id = context.get("bid_id", "") if context else ""
        query = f"playbook for {bid_id}" if bid_id else "general bid response playbook"
        
        knowledge = store.retrieve(query, top_k=3)
        
        ctx = f"\n\nContext: {json.dumps(context, indent=2, default=str)}" if context else ""
        
        knowledge_section = "\n\n## Relevant Knowledge from Base:\n"
        for k in knowledge:
            knowledge_section += f"\n### {k['title']} (v{k['version']}, sim: {k['similarity']:.2f})\n"
            knowledge_section += k['content'][:1000] + "\n"
        
        return f"{task}{ctx}{knowledge_section}"