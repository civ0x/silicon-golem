"""Tests for the skill library.

Covers:
1. Save and retrieve by name
2. Search relevance ranking (name match > description match)
3. filter_by_level correctly excludes skills with above-level concepts
4. record_use increments counter
5. Delete
6. Persistence round-trip (save, reload, verify)
7. Duplicate name handling (update preserves created/times_used)
8. Empty library edge cases
9. list_all ordering
10. Unknown concepts excluded by filter_by_level
"""

import json
from pathlib import Path

import pytest

from golem.skills import Skill, SkillLibrary, _concepts_within_level


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def lib_path(tmp_path: Path) -> str:
    return str(tmp_path / "skills.json")


@pytest.fixture
def lib(lib_path: str) -> SkillLibrary:
    return SkillLibrary(library_path=lib_path)


def _add_wall_skill(lib: SkillLibrary) -> Skill:
    return lib.save_skill(
        name="build_wall",
        source="def build_wall(length, height, block='cobblestone'):\n    for i in range(length):\n        build_line(height, block)",
        description="Builds a straight wall of specified dimensions",
        concepts=["for_loops", "variables"],
        author="bot",
    )


def _add_tower_skill(lib: SkillLibrary) -> Skill:
    return lib.save_skill(
        name="build_tower",
        source="def build_tower(height, block='cobblestone'):\n    for i in range(height):\n        place_block(block)",
        description="Builds a vertical tower",
        concepts=["for_loops", "variables"],
        author="bot",
    )


def _add_simple_skill(lib: SkillLibrary) -> Skill:
    """A level 1 skill (no loops, no conditionals)."""
    return lib.save_skill(
        name="place_cobblestone",
        source="place_block('cobblestone')",
        description="Places a single cobblestone block",
        concepts=["function_calls"],
        author="kid",
    )


def _add_function_skill(lib: SkillLibrary) -> Skill:
    """A level 3 skill (function_definitions)."""
    return lib.save_skill(
        name="make_bridge",
        source="def make_bridge(length):\n    for i in range(length):\n        place_block('oak_planks')\n    return length",
        description="Builds a bridge and returns its length",
        concepts=["function_definitions", "for_loops", "return_values"],
        author="bot",
    )


# ── Save and Retrieve ────────────────────────────────────────────────────────

class TestSaveAndRetrieve:
    def test_save_and_get(self, lib: SkillLibrary) -> None:
        skill = _add_wall_skill(lib)
        assert skill.name == "build_wall"
        assert skill.times_used == 0
        assert skill.author == "bot"

        retrieved = lib.get_skill("build_wall")
        assert retrieved is not None
        assert retrieved.source == skill.source
        assert retrieved.description == skill.description
        assert retrieved.concepts == ["for_loops", "variables"]

    def test_get_nonexistent(self, lib: SkillLibrary) -> None:
        assert lib.get_skill("does_not_exist") is None

    def test_save_sets_timestamp(self, lib: SkillLibrary) -> None:
        skill = _add_wall_skill(lib)
        # Should be a valid ISO timestamp
        dt = skill.created
        assert "T" in dt
        assert "+" in dt or "Z" in dt or dt.endswith("+00:00")


# ── Duplicate Name Handling ──────────────────────────────────────────────────

class TestDuplicateNames:
    def test_update_preserves_created_and_times_used(self, lib: SkillLibrary) -> None:
        original = _add_wall_skill(lib)
        original_created = original.created
        lib.record_use("build_wall")
        lib.record_use("build_wall")

        # Update with same name
        updated = lib.save_skill(
            name="build_wall",
            source="def build_wall(l, h):\n    pass",
            description="Updated wall builder",
            concepts=["for_loops"],
            author="modified",
        )

        assert updated.created == original_created
        assert updated.times_used == 2
        assert updated.source == "def build_wall(l, h):\n    pass"
        assert updated.author == "modified"
        assert updated.description == "Updated wall builder"

    def test_update_changes_concepts(self, lib: SkillLibrary) -> None:
        _add_wall_skill(lib)
        lib.save_skill(
            name="build_wall",
            source="place_block('cobblestone')",
            description="Simplified wall",
            concepts=["function_calls"],
            author="kid",
        )
        skill = lib.get_skill("build_wall")
        assert skill is not None
        assert skill.concepts == ["function_calls"]


# ── Search ───────────────────────────────────────────────────────────────────

class TestSearch:
    def test_name_match_ranks_higher_than_description(self, lib: SkillLibrary) -> None:
        _add_wall_skill(lib)
        _add_tower_skill(lib)
        # "wall" appears in build_wall's name, not in build_tower
        results = lib.search("wall")
        assert len(results) >= 1
        assert results[0].name == "build_wall"

    def test_search_case_insensitive(self, lib: SkillLibrary) -> None:
        _add_wall_skill(lib)
        results = lib.search("WALL")
        assert len(results) == 1
        assert results[0].name == "build_wall"

    def test_search_multiple_tokens(self, lib: SkillLibrary) -> None:
        _add_wall_skill(lib)
        _add_tower_skill(lib)
        # "build" matches both names; "wall" matches only build_wall
        results = lib.search("build wall")
        assert results[0].name == "build_wall"

    def test_search_description_match(self, lib: SkillLibrary) -> None:
        _add_wall_skill(lib)
        # "straight" only in description
        results = lib.search("straight")
        assert len(results) == 1
        assert results[0].name == "build_wall"

    def test_search_no_results(self, lib: SkillLibrary) -> None:
        _add_wall_skill(lib)
        results = lib.search("diamond pickaxe")
        assert results == []

    def test_search_empty_query(self, lib: SkillLibrary) -> None:
        _add_wall_skill(lib)
        results = lib.search("")
        assert results == []

    def test_search_limit(self, lib: SkillLibrary) -> None:
        for i in range(10):
            lib.save_skill(
                name=f"build_{i}",
                source=f"pass",
                description=f"Build thing {i}",
                concepts=["variables"],
                author="bot",
            )
        results = lib.search("build", limit=3)
        assert len(results) == 3

    def test_search_tiebreak_by_times_used(self, lib: SkillLibrary) -> None:
        _add_wall_skill(lib)
        _add_tower_skill(lib)
        # Both have "build" in name; give tower more uses
        lib.record_use("build_tower")
        lib.record_use("build_tower")
        lib.record_use("build_tower")
        results = lib.search("build")
        # Both score equally on "build", tower should win tiebreak
        assert results[0].name == "build_tower"


# ── Filter by Level ──────────────────────────────────────────────────────────

class TestFilterByLevel:
    def test_level_1_includes_simple_skill(self, lib: SkillLibrary) -> None:
        _add_simple_skill(lib)
        results = lib.filter_by_level(1)
        assert len(results) == 1
        assert results[0].name == "place_cobblestone"

    def test_level_1_excludes_loop_skill(self, lib: SkillLibrary) -> None:
        _add_wall_skill(lib)  # has for_loops (level 2)
        results = lib.filter_by_level(1)
        assert len(results) == 0

    def test_level_2_includes_loop_skill(self, lib: SkillLibrary) -> None:
        _add_wall_skill(lib)
        _add_simple_skill(lib)
        results = lib.filter_by_level(2)
        assert len(results) == 2

    def test_level_2_excludes_function_def_skill(self, lib: SkillLibrary) -> None:
        _add_function_skill(lib)  # has function_definitions (level 3)
        results = lib.filter_by_level(2)
        assert len(results) == 0

    def test_level_3_includes_all(self, lib: SkillLibrary) -> None:
        _add_simple_skill(lib)
        _add_wall_skill(lib)
        _add_function_skill(lib)
        results = lib.filter_by_level(3)
        assert len(results) == 3

    def test_unknown_concept_excluded(self, lib: SkillLibrary) -> None:
        lib.save_skill(
            name="magic",
            source="magic()",
            description="Does magic",
            concepts=["teleportation"],  # not in CONCEPT_REGISTRY
            author="bot",
        )
        results = lib.filter_by_level(5)
        assert len(results) == 0

    def test_empty_concepts_included_at_all_levels(self, lib: SkillLibrary) -> None:
        lib.save_skill(
            name="noop",
            source="pass",
            description="Does nothing",
            concepts=[],
            author="bot",
        )
        assert len(lib.filter_by_level(1)) == 1
        assert len(lib.filter_by_level(2)) == 1
        assert len(lib.filter_by_level(3)) == 1


# ── Record Use ───────────────────────────────────────────────────────────────

class TestRecordUse:
    def test_increment(self, lib: SkillLibrary) -> None:
        _add_wall_skill(lib)
        lib.record_use("build_wall")
        assert lib.get_skill("build_wall").times_used == 1
        lib.record_use("build_wall")
        assert lib.get_skill("build_wall").times_used == 2

    def test_nonexistent_skill_no_error(self, lib: SkillLibrary) -> None:
        # Should silently do nothing
        lib.record_use("ghost_skill")


# ── Delete ───────────────────────────────────────────────────────────────────

class TestDelete:
    def test_delete_existing(self, lib: SkillLibrary) -> None:
        _add_wall_skill(lib)
        assert lib.delete_skill("build_wall") is True
        assert lib.get_skill("build_wall") is None

    def test_delete_nonexistent(self, lib: SkillLibrary) -> None:
        assert lib.delete_skill("ghost") is False

    def test_delete_persists(self, lib: SkillLibrary, lib_path: str) -> None:
        _add_wall_skill(lib)
        _add_tower_skill(lib)
        lib.delete_skill("build_wall")
        # Reload
        lib2 = SkillLibrary(library_path=lib_path)
        assert lib2.get_skill("build_wall") is None
        assert lib2.get_skill("build_tower") is not None


# ── Persistence ──────────────────────────────────────────────────────────────

class TestPersistence:
    def test_round_trip(self, lib: SkillLibrary, lib_path: str) -> None:
        skill = _add_wall_skill(lib)
        lib.record_use("build_wall")

        # Reload from disk
        lib2 = SkillLibrary(library_path=lib_path)
        loaded = lib2.get_skill("build_wall")
        assert loaded is not None
        assert loaded.name == skill.name
        assert loaded.source == skill.source
        assert loaded.description == skill.description
        assert loaded.concepts == skill.concepts
        assert loaded.author == skill.author
        assert loaded.created == skill.created
        assert loaded.times_used == 1

    def test_creates_directory_if_missing(self, tmp_path: Path) -> None:
        deep_path = str(tmp_path / "a" / "b" / "skills.json")
        lib = SkillLibrary(library_path=deep_path)
        _add_wall_skill(lib)
        assert Path(deep_path).exists()

    def test_json_format(self, lib: SkillLibrary, lib_path: str) -> None:
        _add_wall_skill(lib)
        data = json.loads(Path(lib_path).read_text())
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "build_wall"
        assert "source" in data[0]
        assert "created" in data[0]


# ── List All ─────────────────────────────────────────────────────────────────

class TestListAll:
    def test_sorted_by_times_used(self, lib: SkillLibrary) -> None:
        _add_wall_skill(lib)
        _add_tower_skill(lib)
        _add_simple_skill(lib)
        lib.record_use("place_cobblestone")
        lib.record_use("place_cobblestone")
        lib.record_use("build_tower")

        results = lib.list_all()
        assert results[0].name == "place_cobblestone"
        assert results[1].name == "build_tower"
        assert results[2].name == "build_wall"

    def test_empty_library(self, lib: SkillLibrary) -> None:
        assert lib.list_all() == []


# ── Empty Library Edge Cases ─────────────────────────────────────────────────

class TestEmptyLibrary:
    def test_search_empty(self, lib: SkillLibrary) -> None:
        assert lib.search("anything") == []

    def test_filter_empty(self, lib: SkillLibrary) -> None:
        assert lib.filter_by_level(1) == []

    def test_list_all_empty(self, lib: SkillLibrary) -> None:
        assert lib.list_all() == []

    def test_get_empty(self, lib: SkillLibrary) -> None:
        assert lib.get_skill("anything") is None

    def test_delete_empty(self, lib: SkillLibrary) -> None:
        assert lib.delete_skill("anything") is False


# ── Helper Function ──────────────────────────────────────────────────────────

class TestConceptsWithinLevel:
    def test_level_1_concepts(self) -> None:
        assert _concepts_within_level(["variables", "function_calls"], 1) is True

    def test_level_2_concept_at_level_1(self) -> None:
        assert _concepts_within_level(["for_loops"], 1) is False

    def test_level_2_concept_at_level_2(self) -> None:
        assert _concepts_within_level(["for_loops"], 2) is True

    def test_mixed_levels(self) -> None:
        assert _concepts_within_level(["variables", "for_loops"], 1) is False
        assert _concepts_within_level(["variables", "for_loops"], 2) is True

    def test_empty_concepts(self) -> None:
        assert _concepts_within_level([], 1) is True

    def test_unknown_concept(self) -> None:
        assert _concepts_within_level(["teleportation"], 5) is False
