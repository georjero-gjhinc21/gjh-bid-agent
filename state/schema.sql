-- Shared state for all agents. Each agent reads/writes a narrow slice.

CREATE TABLE IF NOT EXISTS opportunities (
    id              TEXT PRIMARY KEY,         -- hash of source+ref
    source          TEXT NOT NULL,            -- 'gmail' | 'web' | 'manual'
    source_detail   TEXT,                     -- sender or URL
    title           TEXT NOT NULL,
    buyer           TEXT,                     -- 'M-DCPS', 'City of X', etc.
    bid_number      TEXT,                     -- ITB/RFQ/RFP number
    deadline        TEXT,                     -- ISO date if known
    url             TEXT,
    raw_text        TEXT,                     -- snippet/body
    discovered_at   TEXT NOT NULL,            -- ISO timestamp
    fit_score       INTEGER,                  -- 0-100, set by Scout
    fit_rationale   TEXT,                     -- one sentence
    status          TEXT NOT NULL DEFAULT 'new'  -- new|analyzing|to_bid|skip|won|lost
);

CREATE INDEX IF NOT EXISTS idx_opp_status ON opportunities(status);
CREATE INDEX IF NOT EXISTS idx_opp_discovered ON opportunities(discovered_at);

CREATE TABLE IF NOT EXISTS analyses (
    opp_id          TEXT PRIMARY KEY REFERENCES opportunities(id),
    requirements    TEXT,                     -- JSON list
    mandatory_forms TEXT,                     -- JSON list
    eval_criteria   TEXT,
    risks           TEXT,                     -- JSON list
    contact_name    TEXT,
    contact_email   TEXT,
    analyzed_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS strategies (
    opp_id          TEXT PRIMARY KEY REFERENCES opportunities(id),
    recommendation  TEXT NOT NULL,            -- bid | no_bid | watch
    rationale       TEXT,
    pricing_posture TEXT,                     -- aggressive | market | premium
    teaming_notes   TEXT,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contacts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    org             TEXT,
    email           TEXT,
    phone           TEXT,
    role            TEXT,
    last_contact    TEXT,
    next_followup   TEXT,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS compliance_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    renews          TEXT,                     -- ISO date or 'monthly' etc.
    owner           TEXT,
    last_done       TEXT,
    next_due        TEXT,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    agent           TEXT NOT NULL,
    started_at      TEXT NOT NULL,
    ended_at        TEXT,
    status          TEXT,                     -- ok | error
    summary         TEXT,
    error           TEXT
);

CREATE TABLE IF NOT EXISTS digests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sent_at         TEXT NOT NULL,
    body            TEXT
);
