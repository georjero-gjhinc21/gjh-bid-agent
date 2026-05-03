# GJH Bid Agent — Autonomous Bid Response System

An always-on, self-improving agentic system for winning and executing public-sector bids.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              ORCHESTRATOR                                   │
│                   (coordinates agents, manages workflow)                    │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌───────────────┐      ┌───────────────┐      ┌───────────────┐
│   PLANNER     │      │   EXECUTOR    │      │    CRITIC     │
│   Agent       │      │   Agent       │      │    Agent      │
│ (creates      │      │ (executes     │      │ (adversarial  │
│  workflows)   │      │  steps)       │      │  evaluation)  │
└───────┬───────┘      └───────┬───────┘      └───────┬───────┘
        │                       │                       │
        └───────────────────────┴───────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌───────────────┐      ┌───────────────┐      ┌───────────────┐
│   KNOWLEDGE   │      │    MEMORY     │      │   TELEMETRY   │
│    Base       │      │    Store      │      │   + Guards    │
│ (playbooks,   │      │ (episodic,    │      │ (LLM logs,    │
│  lessons,     │      │  semantic,    │      │  cost caps,   │
│  templates)   │      │  procedural) │      │  HITL gate)   │
└───────────────┘      └───────────────┘      └───────────────┘
```

## Core Agents

| Agent | Role | Status |
|-------|------|--------|
| **Orchestrator** | Coordinates daily runs and workflow execution | full |
| **Planner** | Creates dynamic workflows from solicitation documents | full |
| **BidExecutor** | Executes workflow steps using knowledge base | full |
| **Critic** | Adversarial evaluation with retry loop (max 3) | full |
| **Learner** | Post-mortem and proposed knowledge improvements | full |
| **GoalAgent** | Goal decomposition and sub-goal tracking | full |
| **Scout** | Discovers opportunities from inbox + web | full |
| **Analyst** | Parses solicitation documents | scaffold |
| **Strategist** | Bid/no-bid recommendations | scaffold |
| **Compliance** | Watches expiries, filings, licenses | partial |
| **Drafter** | Generates response packages | scaffold |

## Key Features

### 1. Knowledge Base (No Hardcoded Facts)
- Playbooks, lessons, and templates stored in `knowledge/`
- Semantic search via KnowledgeStore (SQLite + embeddings)
- Agents retrieve relevant knowledge at runtime

### 2. Dynamic Workflows (Data-Driven)
- PlannerAgent creates workflow JSON from solicitation
- Workflow stored as data, not hardcoded steps
- Different solicitations get different plans

### 3. Self-Critique Loop
- CriticAgent evaluates each deliverable against success criteria
- Max 3 retries if issues found (severity >= medium)
- Critiques saved for learning

### 4. Three-Tier Memory
- **Episodic**: JSONL log per run (actions, decisions)
- **Semantic**: Extracted facts with expiration
- **Procedural**: Refined prompts/templates that worked

### 5. Learning Loop
- LearnerAgent runs post-mortem after each bid outcome
- Proposes changes to knowledge base
- HITL approval for accepting/rejecting changes

### 6. Guardrails
- **Cost ceiling**: $25/run (configurable)
- **HITL approval**: Required for submit/sign/send/spend actions
- **Cone of Silence**: Blocks contact with board members during solicitations

## Usage

```bash
# Daily digest run
python main.py

# Run bid workflow for specific solicitation
python main.py --bid ITB-23-014-JW

# Create workflow plan for new solicitation
python main.py --plan ITB-25-001-AB --solicitation-file /path/to/doc.pdf

# Check workflow status
python main.py --status ITB-23-014-JW

# Run post-mortem after bid outcome
python main.py --learn --bid ITB-23-014-JW --outcome lost
```

## How to Add a New Bid

1. **Add solicitation document** to working directory
2. **Run planner** to create workflow:
   ```
   python main.py --plan SOLICITATION_ID --solicitation-file doc.pdf
   ```
3. **Execute workflow**:
   ```
   python main.py --bid SOLICITATION_ID
   ```
4. **System retrieves** relevant playbooks/lessons from knowledge base
5. **Critic evaluates** each step, retries if needed
6. **Learner post-mortem** after outcome

## Learning Loop

```
Bid Completed → LearnerAgent Post-Mortem → Proposed Changes 
                                              ↓
                              Human Review (HITL)
                              ↓           ↓
                          Approved    Rejected
                              ↓
                    Update Knowledge Base
```

After N approved changes, run regression test:
```bash
python tests/test_integration.py
```

## Setup

```bash
cp .env.example .env          # fill in secrets
pip install -r requirements.txt
python main.py                # test run
```

## Secrets

- `ANTHROPIC_API_KEY` - Claude API
- `GMAIL_USER` / `GMAIL_APP_PASSWORD` - for digest emails
- `DIGEST_TO` - recipient (defaults to GMAIL_USER)

## Architecture Notes

- Agents use tool-use loop (not prompt engineering alone)
- Every LLM call logged with tokens, cost, latency
- No agent submits to external parties without HITL approval
- Backward compatible: `python main.py --bid` still works