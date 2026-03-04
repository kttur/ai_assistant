from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field


@dataclass(slots=True, frozen=True)
class SkillCommandSpec:
    """Declarative command metadata exposed to the LLM."""

    command: str
    description: str
    args: Mapping[str, object] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class SkillSpec:
    """Declarative skill metadata for registry/discovery."""

    skill_id: str
    title: str
    llm_description: str
    commands: tuple[SkillCommandSpec, ...]


SkillExecuteFn = Callable[[str, dict[str, object]], dict[str, object]]


@dataclass(slots=True)
class ExecutableSkill:
    """Runtime wrapper combining skill declaration and execution callback."""

    spec: SkillSpec
    execute: SkillExecuteFn
