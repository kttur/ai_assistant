# AGENTS

## Start-Of-Chat Checklist

1. Read `docs/CODEX_START.md`.
2. Read `context/CODEX_CONTEXT.md`.
3. Do **not** deep-scan `.venv` (or `.git`/cache dirs) during project analysis.

## Documentation Sync Rule

- After structural changes in `src/`, `tests/`, `docs/`, or `context/`, run:
  - `python -m ai_assistant.devtools.sync_docs`
- Before finalizing substantial changes, ensure check mode passes:
  - `python -m ai_assistant.devtools.sync_docs --check`

## Environment Variable Sync Rule

- If you add, remove, or rename any environment variable used by the app, update `.env.example` in the same change.
- Keep default values and comments in `.env.example` aligned with `src/ai_assistant/config/settings.py`.

## Python Execution Rule

- If `.venv` exists in the repository root, run Python tools via this environment.
- Prefer:
  - `.venv\Scripts\python.exe -m ...` on Windows
  - `.venv/bin/python -m ...` on Unix-like systems
- Applies to commands such as `pytest`, `sync_docs`, and other project Python entry points.

## Priority Sources

- Project map: `docs/PROJECT_MAP.md` (auto-generated).
- Architecture guide: `docs/ARCHITECTURE.md`.
- Dev rules: `docs/DEVELOPMENT_GUIDELINES.md`.
- Runtime context: `context/CODEX_CONTEXT.md` (auto-generated).

## Performance & Optimization Notes

### LLM Router System

**Key Files:**
- Router logic: `src/ai_assistant/providers/llm/auto_router.py`
- Router prompts: `src/ai_assistant/providers/llm/auto_router_policy.py`
- Model health: `src/ai_assistant/providers/llm/model_health_registry.py`
- Model manifest: `context/model_manifest.json`

**Configuration (from `.env`):**
- Quick command timeout: `3.0s` (was 1.25s)
- Health cooldown: base `30s`, max `300s` (was 120s/1800s)
- Router uses `/nothink` directive for qwen3 models

**Quick Command Mode:**
- Enabled for commands matching patterns in `auto_router.py:_QUICK_COMMAND_HINTS`
- Uses minimal prompt: only `provider`, `model`, `cost_tier`, `priority`, `strength`
- Skips verbose metadata: `abilities`, `tags`, `domains`, `notes`, etc.

**Optimization Strategy:**
1. **For simple commands** ("pause", "play"): use quick mode with minimal catalog
2. **For complex requests**: use full catalog with all metadata
3. Router selects models by `priority` (lower = better) and `strength` (higher = better for complex)

### Main LLM Prompts

**Core Service:** `src/ai_assistant/core/service.py`

**Optimized Prompts:**
- System: "Ты AI-помощник. Учитывай историю и отвечай на последнее сообщение."
- Commands: "Commands:" (was "Available commands JSON:")
- Tool results: "Результаты команд:" (was "Результаты выполнения команд (JSON):")
- Language: "Reply in Russian unless user asks otherwise."

**Token Savings:**
- Router prompt (quick mode): ~76% reduction
- Main prompt: ~30% reduction
- Followup prompt: ~30% reduction
- **Total for simple commands: ~60% token reduction**

### Testing After Changes

Always run full test suite after modifying:
- Router prompts or policy
- Model manifest
- Core service prompts
- Health registry settings

```bash
.venv/Scripts/python -m pytest tests/ -v
```

Key test files:
- `tests/core/test_assistant_service.py` - prompt format validation
- `tests/providers/llm/test_auto_router.py` - router behavior
- `tests/providers/llm/test_auto_router_policy.py` - prompt extraction

### Model Manifest Structure

**Location:** `context/model_manifest.json`

**Required fields:**
- `provider`, `model`, `roles`, `platform`, `cost_tier`
- `priority`, `strength`
- `supports_reasoning`, `supports_non_reasoning`

**Optional but used:**
- `abilities` - for full mode routing decisions
- `tags` - for specialized routing (medical, coding)
- `domains` - for domain-specific routing
- `notes` - human-readable description (used in full mode)

**Keep minimal** to reduce token usage, especially for frequently-used models.
