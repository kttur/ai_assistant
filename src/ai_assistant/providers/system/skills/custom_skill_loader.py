from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass

from ai_assistant.core.interfaces import MPCController, MediaController, OutputController
from ai_assistant.skills.models import ExecutableSkill

SkillFactory = Callable[["SystemSkillFactoryContext"], ExecutableSkill | None]


@dataclass(slots=True, frozen=True)
class SystemSkillFactoryContext:
    media_controller: MediaController | None
    mpc_controller: MPCController | None
    output_controller: OutputController | None


def load_custom_system_skills(
    factory_paths: tuple[str, ...],
    context: SystemSkillFactoryContext,
) -> list[ExecutableSkill]:
    skills: list[ExecutableSkill] = []
    for raw_path in factory_paths:
        path = raw_path.strip()
        if not path:
            continue

        module_path, sep, attribute_name = path.partition(":")
        if not module_path:
            raise ValueError(f"Invalid skill factory path: {raw_path}")
        if not sep:
            attribute_name = "build_skill"

        module = importlib.import_module(module_path)
        factory = getattr(module, attribute_name, None)
        if factory is None or not callable(factory):
            raise ValueError(f"Skill factory is not callable: {path}")

        skill = factory(context)
        if skill is None:
            continue
        if not isinstance(skill, ExecutableSkill):
            raise TypeError(
                f"Skill factory {path} returned unsupported value type: {type(skill)!r}"
            )
        skills.append(skill)

    return skills
