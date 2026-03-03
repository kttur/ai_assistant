# Roadmap

## Stage 0 - Foundation (done)

- [x] Create a modular project skeleton.
- [x] Add Telegram module and test commands.
- [x] Add architecture/context documentation.
- [x] Split large Telegram handlers/test modules into smaller files.
- [x] Add generated project map and Codex context sync tooling.

## Stage 1 - LLM Integration (mostly done)

- [x] Implement OpenAI provider.
- [x] Implement Anthropic provider.
- [x] Implement Ollama provider.
- [x] Provider switching via config without changing channels/core.
- [ ] Add robust auto-routing mode (`llm_provider=auto`) with policies/fallbacks.

## Stage 2 - Memory and History

- [ ] Add persistent history storage (SQLite/PostgreSQL).
- [ ] Introduce short-term and long-term memory strategy.
- [ ] Context retention/summarization policy.

## Stage 3 - Multi-channel

- [ ] Android API/WS channel.
- [ ] Voice pipeline (ASR -> orchestration -> TTS).
- [ ] Image processing (OCR/VLM).

## Stage 4 - Multi-user and Access

- [x] Permission model (user + role + effective resolution).
- [ ] Context isolation policies and profile settings.
- [ ] Audit trail for sensitive actions with local/external resources.
