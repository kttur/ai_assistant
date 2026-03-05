from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class ModelManifestEntry:
    provider: str
    model: str
    roles: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    domains: tuple[str, ...] = ()
    platform: str | None = None
    cost_tier: str | None = None
    notes: str = ""
    priority: int = 100
    strength: int = 0
    supports_reasoning: bool = True
    supports_non_reasoning: bool = True
    abilities: tuple[str, ...] = ()


def manifest_entry_key(provider: str, model: str) -> tuple[str, str]:
    return provider.strip().lower(), model.strip().lower()


def build_manifest_index(
    entries: tuple[ModelManifestEntry, ...],
) -> dict[tuple[str, str], ModelManifestEntry]:
    return {manifest_entry_key(entry.provider, entry.model): entry for entry in entries}


def models_for_provider(
    entries: tuple[ModelManifestEntry, ...],
    provider: str,
) -> tuple[str, ...]:
    normalized_provider = provider.strip().lower()
    models: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        if entry.provider != normalized_provider:
            continue
        normalized_model = entry.model.strip().lower()
        if not normalized_model or normalized_model in seen:
            continue
        seen.add(normalized_model)
        models.append(entry.model)
    return tuple(models)


def load_model_manifest(path: str) -> tuple[ModelManifestEntry, ...]:
    cleaned_path = path.strip()
    if not cleaned_path:
        return ()

    manifest_path = Path(cleaned_path)
    try:
        mtime_ns = manifest_path.stat().st_mtime_ns
    except FileNotFoundError:
        logger.warning("Model manifest file not found: %s", manifest_path)
        return ()
    except OSError as exc:
        logger.warning("Failed to access model manifest %s: %s", manifest_path, exc)
        return ()

    return _load_model_manifest_cached(str(manifest_path), mtime_ns)


@lru_cache(maxsize=16)
def _load_model_manifest_cached(path: str, mtime_ns: int) -> tuple[ModelManifestEntry, ...]:
    del mtime_ns  # Cache invalidation key, included intentionally.
    manifest_path = Path(path)
    try:
        raw_text = manifest_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("Model manifest file not found: %s", manifest_path)
        return ()
    except OSError as exc:
        logger.warning("Failed to read model manifest %s: %s", manifest_path, exc)
        return ()

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse model manifest %s: %s", manifest_path, exc)
        return ()

    if not isinstance(payload, dict):
        logger.warning("Model manifest payload is not a JSON object: %s", manifest_path)
        return ()

    raw_models = payload.get("models")
    if not isinstance(raw_models, list):
        logger.warning("Model manifest does not contain a models list: %s", manifest_path)
        return ()

    entries: list[ModelManifestEntry] = []
    seen: set[tuple[str, str]] = set()
    for raw_item in raw_models:
        if not isinstance(raw_item, dict):
            continue
        provider = str(raw_item.get("provider", "")).strip().lower()
        model = str(raw_item.get("model", "")).strip()
        if not provider or not model:
            continue
        key = manifest_entry_key(provider, model)
        if key in seen:
            continue
        seen.add(key)
        entries.append(
            ModelManifestEntry(
                provider=provider,
                model=model,
                roles=_normalize_string_list(raw_item.get("roles")),
                tags=_normalize_string_list(raw_item.get("tags")),
                domains=_normalize_string_list(raw_item.get("domains")),
                platform=_normalize_optional_string(raw_item.get("platform")),
                cost_tier=_normalize_optional_string(raw_item.get("cost_tier")),
                notes=str(raw_item.get("notes", "")).strip(),
                priority=_normalize_int(raw_item.get("priority"), default=100),
                strength=_normalize_int(raw_item.get("strength"), default=0),
                supports_reasoning=_normalize_bool(raw_item.get("supports_reasoning"), default=True),
                supports_non_reasoning=_normalize_bool(
                    raw_item.get("supports_non_reasoning"),
                    default=True,
                ),
                abilities=_normalize_string_list(raw_item.get("abilities")),
            )
        )

    logger.info("Loaded model manifest: path=%s entries=%d", manifest_path, len(entries))
    return tuple(entries)


def _normalize_optional_string(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    return normalized


def _normalize_string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    items: list[str] = []
    seen: set[str] = set()
    for raw_item in value:
        normalized = str(raw_item).strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        items.append(normalized)
    return tuple(items)


def _normalize_int(value: object, *, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return default
        try:
            return int(cleaned)
        except ValueError:
            return default
    return default


def _normalize_bool(value: object, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return bool(value)
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if not cleaned:
            return default
        if cleaned in {"1", "true", "yes", "on"}:
            return True
        if cleaned in {"0", "false", "no", "off"}:
            return False
    return default
