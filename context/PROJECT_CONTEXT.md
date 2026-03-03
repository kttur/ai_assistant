# Project Context

## Product Vision

A general-purpose home AI assistant for daily work:
- dialogue via text, voice, and photos;
- local computer control;
- integration with external internet resources;
- extensibility through independent modules.

## Planned Interaction Channels

- Telegram (current production channel in this repo);
- Android client (text + voice + photos);
- direct desktop microphone voice input.

## Planned Model Platforms

- OpenAI API;
- Anthropic API;
- Ollama (local models);
- ability to add new providers without changing business logic.

## Core Non-Functional Requirements

- clean modular architecture;
- low coupling between layers;
- easy replacement of DB/LLM/connectors;
- multi-user support (planned);
- storage of important memory and dialogue history (planned).

## Current MVP Scope

- base orchestration layer and composition root;
- Telegram channel with commands, settings UI, terminal mode, media/MPC controls;
- provider selection per user (`llm_provider`, `llm_model`);
- RBAC permissions model;
- OpenAI, Anthropic, Ollama, and mock providers;
- Codex-oriented documentation layer:
  - `docs/CODEX_START.md`
  - `docs/ARCHITECTURE.md`
  - `docs/DEVELOPMENT_GUIDELINES.md`
  - generated `docs/PROJECT_MAP.md`
  - generated `context/CODEX_CONTEXT.md`
