# Git Hooks

This repository includes a pre-commit hook to keep generated docs in sync:

- updates `docs/PROJECT_MAP.md`
- updates `context/CODEX_CONTEXT.md`

## Enable

Run once in the repository root:

```bash
git config core.hooksPath .githooks
```

Then each commit will automatically refresh generated context files.
