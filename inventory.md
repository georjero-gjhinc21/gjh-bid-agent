# SHAKEDOWN INVENTORY — Component Analysis

## Phase 1: Inventory

| Component | Claimed | Actual | Gap |
|-----------|---------|--------|-----|
| **BaseAgent** | Real LLM calls via anthropic | ✅ Actually calls `client.messages.create()` at line 70 in agents/base.py | None |
| **BidExecutorAgent** | Uses KnowledgeStore at runtime | ✅ Actually retrieves knowledge in build_input() | None |
| **PlannerAgent** | Creates dynamic workflows | ⚠️ Calls LLM but returns generic JSON that may not parse as workflow |
| **CriticAgent** | Adversarial evaluation | ✅ Actually evaluates via LLM at agents/critic.py:89 |
| **LearnerAgent** | Post-mortem + proposals | ✅ Actually calls LLM and creates proposed changes |
| **GoalAgent** | Goal decomposition | ✅ Just manages YAML file, no LLM needed |
| **KnowledgeStore** | Semantic search with embeddings | ⚠️ Has embedding logic BUT uses invalid model name `claude-embedding-3-5-20250624` (line 92 in knowledge/store.py). Falls back to LIKE query which works but isn't semantic. |
| **KnowledgeStore.upsert()** | Saves to SQLite + creates embeddings | ⚠️ Embedding fails silently (invalid model), but data saves to SQLite OK |
| **KnowledgeStore.retrieve()** | Semantic search | ⚠️ If no embedding, falls back to SQL LIKE matching (lines 160-171). Works but isn't true semantic. |
| **KnowledgeStore.version()** | Version history | ✅ Works, returns version list from SQLite |
| **MemoryStore (episodic)** | JSONL log per run | ❌ BROKEN: `MEMORY_DIR = Path(__file__).parent / "memory"` (line 21 in memory/store.py) resolves to wrong path `memory/memory/` instead of project root. |
| **MemoryStore (semantic)** | SQLite facts | ✅ Works |
| **MemoryStore (procedural)** | SQLite templates | ✅ Works |
| **Critic retry loop** | Wired into orchestrator | ✅ Actually wired in main.py:69-73 with `should_retry()` check |
| **Telemetry cost ceiling** | $25 hard stop enforced | ❌ NOT WIRED: `log_call()` has the enforcement (line 93-95 in telemetry.py) BUT BaseAgent never calls Telemetry.log_call(). LLM calls go directly through anthropic client. |
| **HITL approval gate** | Blocks submit/sign/send | ❌ NOT WIRED: Telemetry has the methods but they're never called from any agent |
| **Cone of Silence** | Blocks board member contact | ❌ NOT WIRED: check_cone_of_silence exists but not called |
| **ToolRegistry** | Capability-based resolution | ❌ STUB: Registry is empty, no tools registered. get_tool_registry() returns empty dict |
| **PlannerAgent workflow** | Parses PDF | ⚠️ Just takes text string from --solicitation-file, no PDF parsing |
| **Config.MODELS** | Per-agent model selection | ✅ Works, maps agent names to models |
| **requirements.txt** | Dependencies | ⚠️ Missing `anthropic` - line 1 has it but installed packages don't include it in environment |

## Detailed Findings

### 1. BaseAgent (agents/base.py)
- **LLM Calls**: YES - Line 70 `client.messages.create()`
- **Tool execution**: YES - Lines 85-106 handle tool_use loop
- **Imports**: ✅ Satisfied by anthropic package

### 2. KnowledgeStore (knowledge/store.py)
- **Semantic search**: PARTIAL - Uses `_embed_text()` but model name is wrong
- **Model name bug**: Line 92 uses `claude-embedding-3-5-20250624` - this is a future/fake model. Should be `claude-embedding-3-5-20250501` or similar valid model
- **Fallback works**: When embedding fails, LIKE query at lines 161-171 works
- **Persistence**: ✅ SQLite works

### 3. MemoryStore (memory/store.py)
- **Critical bug**: Line 21 - `MEMORY_DIR = Path(__file__).parent / "memory"` resolves to `memory/memory/` because __file__ is in memory/store.py
- **Should be**: `Path(__file__).parent.parent / "memory"`
- **Impact**: Episodic logs written to non-existent directory, silently fails

### 4. Telemetry (telemetry.py)
- **Cost ceiling**: NOT ENFORCED - log_call() has the code but no one calls it
- **HITL**: Methods exist but never called
- **Cone of Silence**: check_cone_of_silence exists but never called
- **Root cause**: BaseAgent doesn't use Telemetry at all

### 5. ToolRegistry (tools/registry.py)
- **Registered tools**: 0 (zero)
- **Used by**: No one
- **Status**: Complete stub

### 6. PlannerAgent (agents/planner.py)
- **Input**: Just text string (no PDF parsing)
- **Output**: Returns JSON but may not be valid workflow JSON

### 7. Workflow (workflow.py)
- **create_default_workflow()**: ✅ Works as fallback
- **from_json()**: ⚠️ Requires valid JSON structure

## What Actually Works (can run without crash)

1. BaseAgent LLM loop ✅
2. KnowledgeStore SQLite storage ✅
3. MemoryStore SQLite (semantic + procedural) ✅
4. Critic retry loop ✅
5. YAML goal management ✅

## What's Broken (causes silent failures or crashes)

1. Memory episodic logging - wrong path
2. KnowledgeStore embeddings - invalid model name
3. Telemetry - not wired to LLM calls
4. ToolRegistry - empty
5. No real solicitation PDF to test with