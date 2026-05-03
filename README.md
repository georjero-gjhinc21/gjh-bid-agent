# GJH Bid Agent — Multi-Agent Framework

An always-on agentic system for winning and executing public-sector bids,
starting with M-DCPS ITB-23-014-JW.

## Architecture

A lead **Orchestrator** delegates to specialist agents. Each specialist is
a real Claude reasoning loop with its own role, system prompt, and tool
set. They share a SQLite state store and communicate via a task queue.

```
                       ┌──────────────────┐
                       │   Orchestrator   │   plans the day, routes work
                       └────────┬─────────┘
            ┌───────────┬───────┼───────┬────────────┬──────────┐
            ▼           ▼       ▼       ▼            ▼          ▼
        ┌───────┐  ┌────────┐ ┌──────┐ ┌────────┐ ┌────────┐ ┌──────────┐
        │Scout  │  │Analyst │ │Strat-│ │Compli- │ │Drafter │ │Relation- │
        │       │  │        │ │egist │ │ance    │ │        │ │ship      │
        └───┬───┘  └────┬───┘ └──┬───┘ └───┬────┘ └───┬────┘ └────┬─────┘
            │           │        │         │          │           │
            └───────────┴────────┴─────────┴──────────┴───────────┘
                                     │
                              ┌──────▼──────┐
                              │  Knowledge  │   shared retrieval
                              │  (vector +  │
                              │   SQLite)   │
                              └─────────────┘
```

| Agent        | Role                                                  | V1 status   |
| ------------ | ----------------------------------------------------- | ----------- |
| Orchestrator | Plans daily run, delegates, assembles digest          | full        |
| Scout        | Discovers new opportunities (Gmail + web sources)     | full        |
| Analyst      | Parses ITB/RFQ docs, extracts requirements & risks    | scaffold    |
| Strategist   | Bid/no-bid recommendation, pricing posture, teaming   | scaffold    |
| Compliance   | Watches COI, OEO reports, filings, license expiries   | partial     |
| Drafter      | Generates response packages (cover, tech, forms)      | scaffold    |
| Relationship | Tracks contacts, drafts outreach with cadence         | scaffold    |
| Knowledge    | Curates and serves the firm KB to other agents        | partial     |

"Scaffold" = full system prompt + role definition + tool stubs in place.
You activate one by implementing its tools, no orchestrator changes needed.

## Why multi-agent and not one script

Each agent has narrow concerns, narrow tools, narrow context. A document
parser does not need access to the email outbox. A compliance watchdog
does not need a vector store. Narrow context means cheaper tokens, fewer
hallucinations, and a clear failure surface — when a digest is wrong you
know which agent produced the wrong output.

Growth happens by adding agents (new source watchers, new buyer
specialists like Broward or Hillsborough) without touching the orchestration
layer. Each agent is independently testable, replaceable, and runnable.

## Daily run

GitHub Actions cron triggers `main.py` once a day. The Orchestrator:

1. Asks Scout to find new opportunities since last run.
2. For each new opportunity, asks Analyst to extract requirements.
3. Asks Strategist for a bid/no-bid call.
4. Asks Compliance for any expiring artifacts or due filings.
5. Asks Relationship for any follow-ups owed.
6. Composes a digest and emails it to the CEO.

Nothing gets submitted, nothing gets sent externally, without human
approval. Three explicit gates: pricing, submission, outbound contact.

## Growth roadmap

- **V1 (now)** — Scout + Orchestrator + daily digest. Compliance flags
  COI/license expiries from local config.
- **V2** — Activate Analyst. When Scout flags an MDCPS RFQ, Analyst pulls
  the doc and produces a structured brief.
- **V3** — Activate Strategist. Bid/no-bid decisions and a draft pricing
  posture appear in the digest.
- **V4** — Activate Drafter. Response packages assembled automatically
  for human review.
- **V5** — Activate Relationship. Contact tracking + outreach drafts.
- **V6** — Add buyer-specialist scouts (Broward, Hillsborough, Orange).
  Each is a Scout subclass; the framework does not change.
- **V7** — Execution agents kick in once you start winning. Project
  intake, milestone tracking, OEO monthly reports.

## Setup

```bash
cp .env.example .env          # fill in secrets
pip install -r requirements.txt
python main.py                # one-shot run
```

Secrets needed:
- `ANTHROPIC_API_KEY`
- `GMAIL_USER` and `GMAIL_APP_PASSWORD` (Google Account → Security →
  2-Step Verification → App passwords)
- `DIGEST_TO` (defaults to `GMAIL_USER`)

Deploy via the included GitHub Actions workflow — set the same names as
repository secrets and the cron runs daily at 11:00 UTC.
