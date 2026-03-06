"""Skill library for Silicon Golem.

Stores, retrieves, searches, and filters saved code skills.
Skills are Python functions composed from SDK calls that the kid or bot
has saved for reuse. Persisted as JSON.

Uses only stdlib: json, dataclasses, datetime, pathlib.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .learner import CONCEPT_REGISTRY


@dataclass
class Skill:
    """A saved code skill."""
    name: str
    source: str
    description: str
    concepts: list[str]
    author: str  # "kid" | "bot" | "modified"
    created: str  # ISO 8601
    times_used: int = 0


class SkillLibrary:
    """Save, search, filter, and manage reusable code skills.

    Persistence: JSON file at library_path.
    Search: keyword matching (v1). Interface supports swapping to
    semantic/embedding search later.
    """

    def __init__(self, library_path: str = "data/skills.json") -> None:
        """Load or create skill library."""
        self._path = Path(library_path)
        self._skills: dict[str, Skill] = {}
        if self._path.exists():
            self._load()

    def _load(self) -> None:
        data = json.loads(self._path.read_text())
        for entry in data:
            self._skills[entry["name"]] = Skill(**entry)

    def save(self) -> None:
        """Persist to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = [asdict(s) for s in self._skills.values()]
        self._path.write_text(json.dumps(data, indent=2) + "\n")

    def save_skill(self, name: str, source: str, description: str,
                   concepts: list[str], author: str) -> Skill:
        """Save a new skill or update existing.

        If a skill with the same name exists, it is overwritten
        (source, description, concepts, author updated; created and
        times_used preserved from the original).
        """
        existing = self._skills.get(name)
        if existing:
            existing.source = source
            existing.description = description
            existing.concepts = list(concepts)
            existing.author = author
            skill = existing
        else:
            skill = Skill(
                name=name,
                source=source,
                description=description,
                concepts=list(concepts),
                author=author,
                created=datetime.now(timezone.utc).isoformat(),
                times_used=0,
            )
            self._skills[name] = skill
        self.save()
        return skill

    def get_skill(self, name: str) -> Skill | None:
        """Get a skill by exact name."""
        return self._skills.get(name)

    def search(self, query: str, limit: int = 5) -> list[Skill]:
        """Search skills by keyword matching against name and description.

        Tokenizes query into words. Each token that appears in the name
        scores 2 points; each token in the description scores 1 point.
        Returns top matches sorted by score descending, then by
        times_used descending as tiebreaker.

        Interface is designed so the retrieval method can be swapped to
        semantic/embedding search by replacing this method's internals.
        """
        tokens = query.lower().split()
        if not tokens:
            return []

        scored: list[tuple[int, int, Skill]] = []
        for skill in self._skills.values():
            name_lower = skill.name.lower()
            desc_lower = skill.description.lower()
            score = 0
            for token in tokens:
                if token in name_lower:
                    score += 2
                if token in desc_lower:
                    score += 1
            if score > 0:
                scored.append((score, skill.times_used, skill))

        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [s[2] for s in scored[:limit]]

    def filter_by_level(self, level: int) -> list[Skill]:
        """Return skills whose concepts are all within the permitted set
        for the given level.

        A concept is available at level N if its level_gate in
        CONCEPT_REGISTRY is <= N. Skills with concepts not in the
        registry are excluded (unknown concepts are not permitted).
        """
        result: list[Skill] = []
        for skill in self._skills.values():
            if _concepts_within_level(skill.concepts, level):
                result.append(skill)
        return result

    def record_use(self, name: str) -> None:
        """Increment times_used for a skill."""
        skill = self._skills.get(name)
        if skill is not None:
            skill.times_used += 1
            self.save()

    def delete_skill(self, name: str) -> bool:
        """Remove a skill. Returns False if not found."""
        if name in self._skills:
            del self._skills[name]
            self.save()
            return True
        return False

    def list_all(self) -> list[Skill]:
        """Return all skills sorted by times_used descending."""
        return sorted(self._skills.values(),
                      key=lambda s: s.times_used, reverse=True)


def _concepts_within_level(concepts: list[str], level: int) -> bool:
    """Check if all concepts are available at the given level."""
    for concept in concepts:
        info = CONCEPT_REGISTRY.get(concept)
        if info is None:
            return False
        if info["level_gate"] > level:
            return False
    return True
