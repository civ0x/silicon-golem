"""Tests for the learner model.

Covers:
1. BKT probability updates (correct and incorrect)
2. Every stage transition (including skip-forward)
3. Prerequisite gating for concept readiness
4. Level promotion logic
5. process_code_displayed detecting concepts from AST
6. Persistence round-trip (save and reload)
7. Disengagement signal handling
8. Edge cases (unknown concepts, events with no concept field)
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from golem.learner import (
    CONCEPT_REGISTRY,
    LEARN_RATES,
    MASTERY_THRESHOLDS,
    P_GUESS,
    P_SLIP,
    STAGES,
    LearnerEvent,
    LearnerModel,
    StateChange,
    _bkt_update,
    _detect_concepts_in_code,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_state_path(tmp_path: Path) -> str:
    return str(tmp_path / "learner_state.json")


@pytest.fixture
def model(tmp_state_path: str) -> LearnerModel:
    return LearnerModel("TestKid", state_path=tmp_state_path)


def _ts(minute: int = 0) -> datetime:
    """Create a timestamp with the given minute for ordering."""
    return datetime(2026, 3, 5, 14, minute, tzinfo=timezone.utc)


def _event(
    event: str,
    concept: str | None = "variables",
    success: bool | None = None,
    context: str = "building",
    minute: int = 0,
    detail: str = "",
) -> LearnerEvent:
    return LearnerEvent(
        event=event,
        concept=concept,
        detail=detail,
        context=context,
        success=success,
        timestamp=_ts(minute),
    )


# ── 1. BKT Probability Updates ───────────────────────────────────────────────

class TestBKTUpdate:
    """Test the BKT forward algorithm."""

    def test_correct_observation_increases_mastery(self) -> None:
        p = _bkt_update(0.0, correct=True, p_learn=0.30)
        assert p > 0.0

    def test_incorrect_observation_still_applies_learn_rate(self) -> None:
        p = _bkt_update(0.0, correct=False, p_learn=0.30)
        # Even with incorrect, learn rate bumps it above zero.
        assert p > 0.0

    def test_correct_increases_more_than_incorrect(self) -> None:
        p_correct = _bkt_update(0.5, correct=True, p_learn=0.15)
        p_incorrect = _bkt_update(0.5, correct=False, p_learn=0.15)
        assert p_correct > p_incorrect

    def test_mastery_approaches_one_with_repeated_correct(self) -> None:
        p = 0.0
        for _ in range(20):
            p = _bkt_update(p, correct=True, p_learn=0.30)
        assert p > 0.95

    def test_mastery_stays_bounded(self) -> None:
        p = 0.0
        for _ in range(100):
            p = _bkt_update(p, correct=True, p_learn=0.30)
        assert p <= 1.0

    def test_from_zero_correct_gives_expected_value(self) -> None:
        # P(L) = 0, correct observation:
        # posterior = (0 * 0.9) / (0 * 0.9 + 1 * 0.2) = 0
        # after learn: 0 + 1 * 0.30 = 0.30
        p = _bkt_update(0.0, correct=True, p_learn=0.30)
        assert abs(p - 0.30) < 1e-9

    def test_from_zero_incorrect_gives_expected_value(self) -> None:
        # P(L) = 0, incorrect observation:
        # posterior = (0 * 0.1) / (0 * 0.1 + 1 * 0.8) = 0
        # after learn: 0 + 1 * 0.30 = 0.30
        p = _bkt_update(0.0, correct=False, p_learn=0.30)
        assert abs(p - 0.30) < 1e-9

    def test_from_half_correct(self) -> None:
        # P(L) = 0.5, correct:
        # posterior = (0.5 * 0.9) / (0.5 * 0.9 + 0.5 * 0.2) = 0.45 / 0.55 ≈ 0.8182
        # after learn (0.15): 0.8182 + 0.1818 * 0.15 ≈ 0.8455
        p = _bkt_update(0.5, correct=True, p_learn=0.15)
        expected_posterior = 0.45 / 0.55
        expected = expected_posterior + (1 - expected_posterior) * 0.15
        assert abs(p - expected) < 1e-9

    def test_from_half_incorrect(self) -> None:
        # P(L) = 0.5, incorrect:
        # posterior = (0.5 * 0.1) / (0.5 * 0.1 + 0.5 * 0.8) = 0.05 / 0.45 ≈ 0.1111
        # after learn (0.15): 0.1111 + 0.8889 * 0.15 ≈ 0.2444
        p = _bkt_update(0.5, correct=False, p_learn=0.15)
        expected_posterior = 0.05 / 0.45
        expected = expected_posterior + (1 - expected_posterior) * 0.15
        assert abs(p - expected) < 1e-9


class TestBKTInModel:
    """Test BKT integration within the LearnerModel."""

    def test_code_modified_correct_updates_mastery(self, model: LearnerModel) -> None:
        # First expose, then modified.
        model._advance_stage("variables", "modified", _ts())
        result = model.process_event(_event("code_modified", success=True, minute=1))
        assert result is not None
        assert result.new_p_mastery > 0.0

    def test_code_modified_incorrect_updates_mastery(self, model: LearnerModel) -> None:
        model._advance_stage("variables", "modified", _ts())
        result = model.process_event(_event("code_modified", success=False, minute=1))
        assert result is not None
        # Should still increase from 0 due to learn rate.
        assert result.new_p_mastery > 0.0

    def test_non_bkt_events_dont_change_mastery(self, model: LearnerModel) -> None:
        model._advance_stage("variables", "exposed", _ts())
        result = model.process_event(_event("code_inspected", minute=1))
        assert result is not None  # Stage changed (exposed -> read).
        assert result.new_p_mastery == 0.0

    def test_observation_counts_increment(self, model: LearnerModel) -> None:
        model._advance_stage("variables", "modified", _ts())
        model.process_event(_event("code_modified", success=True, minute=1))
        model.process_event(_event("code_modified", success=False, minute=2))
        model.process_event(_event("code_modified", success=True, minute=3))
        state = model._concepts["variables"]
        assert state["total_observations"] == 3
        assert state["correct_observations"] == 2


# ── 2. Stage Transitions ─────────────────────────────────────────────────────

class TestStageTransitions:
    """Test every stage transition, including skip-forward."""

    def test_none_to_exposed_via_code_displayed(self, model: LearnerModel) -> None:
        code = 'x = 5\nmove_to(x, 64, 0)\n'
        exposed = model.process_code_displayed(code)
        assert "variables" in exposed
        assert model._concepts["variables"]["stage"] == "exposed"

    def test_exposed_to_read(self, model: LearnerModel) -> None:
        model._advance_stage("variables", "exposed", _ts())
        result = model.process_event(_event("code_inspected", minute=1))
        assert result is not None
        assert result.new_stage == "read"

    def test_exposed_to_read_via_concept_asked(self, model: LearnerModel) -> None:
        model._advance_stage("variables", "exposed", _ts())
        result = model.process_event(_event("concept_asked", minute=1))
        assert result is not None
        assert result.new_stage == "read"

    def test_read_to_modified(self, model: LearnerModel) -> None:
        model._advance_stage("variables", "read", _ts())
        result = model.process_event(_event("code_modified", success=True, minute=1))
        assert result is not None
        assert result.new_stage == "modified"

    def test_modified_to_authored(self, model: LearnerModel) -> None:
        model._advance_stage("variables", "modified", _ts())
        result = model.process_event(_event("code_authored", success=True, minute=1))
        assert result is not None
        assert result.new_stage == "authored"

    def test_authored_to_debugged(self, model: LearnerModel) -> None:
        model._advance_stage("variables", "authored", _ts())
        result = model.process_event(_event("code_debugged", success=True, minute=1))
        assert result is not None
        assert result.new_stage == "debugged"

    def test_debugged_to_composed(self, model: LearnerModel) -> None:
        model._advance_stage("variables", "debugged", _ts())
        result = model.process_event(_event("concept_used", success=True, minute=1))
        assert result is not None
        assert result.new_stage == "composed"

    def test_composed_requires_at_least_authored(self, model: LearnerModel) -> None:
        model._advance_stage("variables", "modified", _ts())
        result = model.process_event(_event("concept_used", success=True, minute=1))
        # Stage should NOT advance to composed (still at modified).
        assert result is not None  # p_mastery changed
        assert model._concepts["variables"]["stage"] == "modified"

    def test_stages_never_go_backward(self, model: LearnerModel) -> None:
        model._advance_stage("variables", "authored", _ts())
        # Trying to go back to "read" should not work.
        model._advance_stage("variables", "read", _ts(1))
        assert model._concepts["variables"]["stage"] == "authored"

    # -- Skip-forward cases --

    def test_skip_exposed_read_modified_to_authored(self, model: LearnerModel) -> None:
        """Kid at 'exposed' authors code — skip to 'authored'."""
        model._advance_stage("variables", "exposed", _ts())
        result = model.process_event(_event("code_authored", success=True, minute=1))
        assert result is not None
        assert result.new_stage == "authored"
        assert result.old_stage == "exposed"

    def test_skip_to_debugged_from_read(self, model: LearnerModel) -> None:
        """Kid at 'read' debugs code — skip to 'debugged'."""
        model._advance_stage("variables", "read", _ts())
        result = model.process_event(_event("code_debugged", success=True, minute=1))
        assert result is not None
        assert result.new_stage == "debugged"

    def test_stage_history_records_transitions(self, model: LearnerModel) -> None:
        model._advance_stage("variables", "exposed", _ts(0))
        model._advance_stage("variables", "read", _ts(5))
        model._advance_stage("variables", "modified", _ts(10))
        history = model._concepts["variables"]["stage_history"]
        assert len(history) == 3
        assert history[0]["stage"] == "exposed"
        assert history[1]["stage"] == "read"
        assert history[2]["stage"] == "modified"


# ── 3. Prerequisite Gating ───────────────────────────────────────────────────

class TestPrerequisiteGating:
    """Test that concept readiness respects prerequisites."""

    def test_no_prereq_concepts_ready_immediately(self, model: LearnerModel) -> None:
        readiness = model.get_concept_readiness()
        intro_concepts = [r["concept"] for r in readiness["ready_to_introduce"]]
        assert "variables" in intro_concepts
        assert "function_calls" in intro_concepts

    def test_concept_with_unmet_prereqs_not_ready(self, model: LearnerModel) -> None:
        readiness = model.get_concept_readiness()
        intro_concepts = [r["concept"] for r in readiness["ready_to_introduce"]]
        # for_loops requires variables at modified stage.
        assert "for_loops" not in intro_concepts

    def test_concept_ready_after_prereqs_met(self, model: LearnerModel) -> None:
        # Advance variables to modified with high mastery.
        model._concepts["variables"]["stage"] = "modified"
        model._concepts["variables"]["p_mastery"] = 0.90
        readiness = model.get_concept_readiness()
        intro_concepts = [r["concept"] for r in readiness["ready_to_introduce"]]
        assert "for_loops" in intro_concepts

    def test_prereqs_reported_as_not_met(self, model: LearnerModel) -> None:
        readiness = model.get_concept_readiness()
        not_met = {r["concept"]: r["missing_prerequisites"]
                   for r in readiness["prerequisites_not_met"]}
        assert "for_loops" in not_met
        assert "variables" in not_met["for_loops"]

    def test_exposed_concept_in_ready_to_advance(self, model: LearnerModel) -> None:
        model._concepts["variables"]["stage"] = "exposed"
        readiness = model.get_concept_readiness()
        advance_concepts = [r["concept"] for r in readiness["ready_to_advance"]]
        assert "variables" in advance_concepts

    def test_composed_concept_not_in_ready_to_advance(self, model: LearnerModel) -> None:
        model._concepts["variables"]["stage"] = "composed"
        readiness = model.get_concept_readiness()
        advance_concepts = [r["concept"] for r in readiness["ready_to_advance"]]
        assert "variables" not in advance_concepts

    def test_chained_prereqs(self, model: LearnerModel) -> None:
        """comparison_operators requires conditionals, which requires variables."""
        readiness = model.get_concept_readiness()
        intro_concepts = [r["concept"] for r in readiness["ready_to_introduce"]]
        assert "comparison_operators" not in intro_concepts

        # Meet variables prereq.
        model._concepts["variables"]["stage"] = "modified"
        model._concepts["variables"]["p_mastery"] = 0.90
        readiness = model.get_concept_readiness()
        intro_concepts = [r["concept"] for r in readiness["ready_to_introduce"]]
        # conditionals is now ready, but comparison_operators still needs conditionals.
        assert "conditionals" in intro_concepts
        assert "comparison_operators" not in intro_concepts


# ── 4. Level Promotion ────────────────────────────────────────────────────────

class TestLevelPromotion:
    """Test level gate logic."""

    def test_starts_at_level_1(self, model: LearnerModel) -> None:
        assert model.get_current_level() == 1

    def test_promote_to_level_2(self, model: LearnerModel) -> None:
        # All Level 1 concepts must be at modified with p_mastery >= 0.85.
        for concept, reg in CONCEPT_REGISTRY.items():
            if reg["level_gate"] <= 1:
                model._concepts[concept]["stage"] = "modified"
                model._concepts[concept]["p_mastery"] = 0.90
        assert model.get_current_level() == 2

    def test_not_promoted_if_mastery_too_low(self, model: LearnerModel) -> None:
        for concept, reg in CONCEPT_REGISTRY.items():
            if reg["level_gate"] <= 1:
                model._concepts[concept]["stage"] = "modified"
                model._concepts[concept]["p_mastery"] = 0.80  # Below 0.85
        assert model.get_current_level() == 1

    def test_not_promoted_if_stage_too_low(self, model: LearnerModel) -> None:
        for concept, reg in CONCEPT_REGISTRY.items():
            if reg["level_gate"] <= 1:
                model._concepts[concept]["stage"] = "read"  # Not modified
                model._concepts[concept]["p_mastery"] = 0.95
        assert model.get_current_level() == 1

    def test_promote_to_level_3(self, model: LearnerModel) -> None:
        # All level_gate <= 2 concepts mastered.
        for concept, reg in CONCEPT_REGISTRY.items():
            if reg["level_gate"] <= 2:
                model._concepts[concept]["stage"] = "modified"
                model._concepts[concept]["p_mastery"] = 0.90
        assert model.get_current_level() == 3

    def test_level_gate_considers_all_lower_levels(self, model: LearnerModel) -> None:
        """Can't skip to level 3 without mastering level 1 concepts."""
        # Only level 2 concepts mastered, not level 1.
        for concept, reg in CONCEPT_REGISTRY.items():
            if reg["level_gate"] == 2:
                model._concepts[concept]["stage"] = "modified"
                model._concepts[concept]["p_mastery"] = 0.90
        assert model.get_current_level() == 1

    def test_promote_to_max_level(self, model: LearnerModel) -> None:
        # All concepts mastered.
        for concept in CONCEPT_REGISTRY:
            model._concepts[concept]["stage"] = "modified"
            model._concepts[concept]["p_mastery"] = 0.95
        assert model.get_current_level() == 5


# ── 5. process_code_displayed ─────────────────────────────────────────────────

class TestCodeDisplayed:
    """Test concept detection from AST in displayed code."""

    def test_detects_variables(self, model: LearnerModel) -> None:
        code = 'x = 5\n'
        exposed = model.process_code_displayed(code)
        assert "variables" in exposed

    def test_detects_function_calls(self, model: LearnerModel) -> None:
        code = 'move_to(1, 2, 3)\n'
        exposed = model.process_code_displayed(code)
        assert "function_calls" in exposed

    def test_detects_attribute_access(self, model: LearnerModel) -> None:
        code = 'x = pos.x\n'
        exposed = model.process_code_displayed(code)
        assert "attribute_access" in exposed

    def test_detects_arithmetic(self, model: LearnerModel) -> None:
        code = 'x = 1 + 2\n'
        exposed = model.process_code_displayed(code)
        assert "arithmetic" in exposed

    def test_detects_string_concatenation(self, model: LearnerModel) -> None:
        code = 'x = "hello" + " world"\n'
        exposed = model.process_code_displayed(code)
        assert "string_concatenation" in exposed

    def test_detects_for_loops(self, model: LearnerModel) -> None:
        code = 'for i in range(5):\n    pass\n'
        exposed = model.process_code_displayed(code)
        assert "for_loops" in exposed

    def test_detects_conditionals(self, model: LearnerModel) -> None:
        code = 'if True:\n    pass\n'
        exposed = model.process_code_displayed(code)
        assert "conditionals" in exposed

    def test_detects_comparison_operators(self, model: LearnerModel) -> None:
        code = 'if x == 5:\n    pass\n'
        exposed = model.process_code_displayed(code)
        assert "comparison_operators" in exposed

    def test_detects_boolean_logic(self, model: LearnerModel) -> None:
        code = 'if x and y:\n    pass\n'
        exposed = model.process_code_displayed(code)
        assert "boolean_logic" in exposed

    def test_detects_function_definitions(self, model: LearnerModel) -> None:
        code = 'def foo():\n    pass\n'
        exposed = model.process_code_displayed(code)
        assert "function_definitions" in exposed

    def test_detects_return_values(self, model: LearnerModel) -> None:
        code = 'def foo():\n    return 5\n'
        exposed = model.process_code_displayed(code)
        assert "return_values" in exposed

    def test_detects_lists(self, model: LearnerModel) -> None:
        code = 'x = [1, 2, 3]\n'
        exposed = model.process_code_displayed(code)
        assert "lists" in exposed

    def test_detects_dictionaries(self, model: LearnerModel) -> None:
        code = 'x = {"a": 1}\n'
        exposed = model.process_code_displayed(code)
        assert "dictionaries" in exposed

    def test_detects_while_loops(self, model: LearnerModel) -> None:
        code = 'while True:\n    pass\n'
        exposed = model.process_code_displayed(code)
        assert "while_loops" in exposed

    def test_detects_string_formatting(self, model: LearnerModel) -> None:
        code = 'x = f"hello {name}"\n'
        exposed = model.process_code_displayed(code)
        assert "string_formatting" in exposed

    def test_only_advances_none_concepts(self, model: LearnerModel) -> None:
        """Already-exposed concepts should not be re-listed."""
        model._concepts["variables"]["stage"] = "read"
        code = 'x = 5\n'
        exposed = model.process_code_displayed(code)
        assert "variables" not in exposed

    def test_syntax_error_returns_empty(self, model: LearnerModel) -> None:
        code = 'def :\n'
        exposed = model.process_code_displayed(code)
        assert exposed == []

    def test_multiple_concepts_in_one_snippet(self, model: LearnerModel) -> None:
        code = '''\
x = 5
move_to(x, 64, x + 1)
'''
        exposed = model.process_code_displayed(code)
        assert "variables" in exposed
        assert "function_calls" in exposed
        assert "arithmetic" in exposed

    def test_str_call_counts_as_string_concatenation(self, model: LearnerModel) -> None:
        code = 'x = str(5) + "hello"\n'
        exposed = model.process_code_displayed(code)
        assert "string_concatenation" in exposed


# ── 6. Persistence Round-Trip ─────────────────────────────────────────────────

class TestPersistence:
    """Test save and reload."""

    def test_save_creates_file(self, model: LearnerModel, tmp_state_path: str) -> None:
        model.save()
        assert Path(tmp_state_path).exists()

    def test_round_trip_preserves_state(self, tmp_state_path: str) -> None:
        model = LearnerModel("TestKid", state_path=tmp_state_path)
        # Modify some state.
        model._advance_stage("variables", "modified", _ts())
        model._concepts["variables"]["p_mastery"] = 0.75
        model._concepts["variables"]["contexts_seen"] = ["building", "mining"]
        model._concepts["variables"]["total_observations"] = 5
        model._concepts["variables"]["correct_observations"] = 4
        model.save()

        # Reload.
        model2 = LearnerModel("TestKid", state_path=tmp_state_path)
        assert model2._concepts["variables"]["stage"] == "modified"
        assert abs(model2._concepts["variables"]["p_mastery"] - 0.75) < 1e-9
        assert model2._concepts["variables"]["contexts_seen"] == ["building", "mining"]
        assert model2._concepts["variables"]["total_observations"] == 5
        assert model2._concepts["variables"]["correct_observations"] == 4

    def test_round_trip_preserves_level(self, tmp_state_path: str) -> None:
        model = LearnerModel("TestKid", state_path=tmp_state_path)
        for concept, reg in CONCEPT_REGISTRY.items():
            if reg["level_gate"] <= 1:
                model._concepts[concept]["stage"] = "modified"
                model._concepts[concept]["p_mastery"] = 0.90
        model.save()

        model2 = LearnerModel("TestKid", state_path=tmp_state_path)
        assert model2.get_current_level() == 2

    def test_round_trip_preserves_session_signals(self, tmp_state_path: str) -> None:
        model = LearnerModel("TestKid", state_path=tmp_state_path)
        model.process_event(_event(
            "disengaged", concept=None, context="building",
            detail="Kid said boring", minute=5,
        ))
        model.save()

        model2 = LearnerModel("TestKid", state_path=tmp_state_path)
        events = model2._session_signals["disengagement_events"]
        assert len(events) == 1
        assert events[0]["detail"] == "Kid said boring"

    def test_round_trip_preserves_stage_history(self, tmp_state_path: str) -> None:
        model = LearnerModel("TestKid", state_path=tmp_state_path)
        model._advance_stage("variables", "exposed", _ts(0))
        model._advance_stage("variables", "read", _ts(5))
        model.save()

        model2 = LearnerModel("TestKid", state_path=tmp_state_path)
        history = model2._concepts["variables"]["stage_history"]
        assert len(history) == 2

    def test_save_creates_parent_directories(self, tmp_path: Path) -> None:
        deep_path = str(tmp_path / "a" / "b" / "state.json")
        model = LearnerModel("TestKid", state_path=deep_path)
        model.save()
        assert Path(deep_path).exists()

    def test_saved_json_has_version(self, model: LearnerModel, tmp_state_path: str) -> None:
        model.save()
        with open(tmp_state_path) as f:
            data = json.load(f)
        assert data["version"] == 1
        assert data["player_name"] == "TestKid"


# ── 7. Disengagement Signals ─────────────────────────────────────────────────

class TestDisengagement:
    """Test disengagement signal handling."""

    def test_disengagement_recorded(self, model: LearnerModel) -> None:
        result = model.process_event(_event(
            "disengaged", concept=None, context="building",
            detail="Kid said boring", minute=5,
        ))
        assert result is None  # No concept state change.
        events = model._session_signals["disengagement_events"]
        assert len(events) == 1
        assert events[0]["current_activity"] == "building"

    def test_disengagement_does_not_affect_bkt(self, model: LearnerModel) -> None:
        # Set up a concept with known mastery.
        model._concepts["variables"]["stage"] = "modified"
        model._concepts["variables"]["p_mastery"] = 0.75
        model.process_event(_event(
            "disengaged", concept=None, context="building",
            detail="bored", minute=1,
        ))
        assert model._concepts["variables"]["p_mastery"] == 0.75

    def test_multiple_disengagements(self, model: LearnerModel) -> None:
        model.process_event(_event(
            "disengaged", concept=None, context="building",
            detail="first", minute=1,
        ))
        model.process_event(_event(
            "disengaged", concept=None, context="mining",
            detail="second", minute=10,
        ))
        events = model._session_signals["disengagement_events"]
        assert len(events) == 2


# ── 8. Edge Cases ─────────────────────────────────────────────────────────────

class TestEdgeCases:
    """Test edge cases: unknown concepts, missing fields, etc."""

    def test_unknown_concept_ignored(self, model: LearnerModel) -> None:
        result = model.process_event(_event(
            "code_modified", concept="quantum_entanglement",
            success=True, minute=1,
        ))
        assert result is None

    def test_none_concept_ignored(self, model: LearnerModel) -> None:
        result = model.process_event(_event(
            "code_modified", concept=None, success=True, minute=1,
        ))
        assert result is None

    def test_context_tracking(self, model: LearnerModel) -> None:
        model._advance_stage("variables", "modified", _ts())
        model.process_event(_event("code_modified", success=True, context="building", minute=1))
        model.process_event(_event("code_modified", success=True, context="mining", minute=2))
        model.process_event(_event("code_modified", success=True, context="building", minute=3))
        assert model._concepts["variables"]["contexts_seen"] == ["building", "mining"]

    def test_get_agent_state_structure(self, model: LearnerModel) -> None:
        state = model.get_agent_state()
        assert "current_level" in state
        assert "concepts" in state
        # Check trimmed view: only stage, p_mastery, contexts_seen.
        for concept_state in state["concepts"].values():
            assert set(concept_state.keys()) == {"stage", "p_mastery", "contexts_seen"}

    def test_get_agent_state_rounds_mastery(self, model: LearnerModel) -> None:
        model._concepts["variables"]["p_mastery"] = 0.123456789
        state = model.get_agent_state()
        assert state["concepts"]["variables"]["p_mastery"] == 0.1235

    def test_new_model_has_all_concepts(self, model: LearnerModel) -> None:
        for concept in CONCEPT_REGISTRY:
            assert concept in model._concepts

    def test_process_event_returns_none_when_nothing_changes(self, model: LearnerModel) -> None:
        # code_inspected on a concept at "none" — target is "read", but we're
        # at "none", so we jump from none to read. Let's test a truly no-op
        # case: event with no target stage mapping and no BKT effect.
        # Actually, code_inspected maps to "read" which is > "none", so it will
        # advance. Let's use a concept already at "read" receiving code_inspected.
        model._concepts["variables"]["stage"] = "read"
        result = model.process_event(_event("code_inspected", minute=1))
        # Stage stays at "read" (already there), no BKT effect.
        assert result is None

    def test_error_encountered_only_bkt_no_stage_advance(self, model: LearnerModel) -> None:
        """error_encountered doesn't map to a stage transition."""
        model._concepts["variables"]["stage"] = "modified"
        result = model.process_event(_event(
            "error_encountered", success=False, minute=1,
        ))
        # BKT should update but stage stays the same.
        assert result is not None
        assert result.new_stage == "modified"
        assert result.new_p_mastery > 0.0  # Learn rate applied.

    def test_success_none_skips_bkt(self, model: LearnerModel) -> None:
        """Events with success=None don't update BKT."""
        model._concepts["variables"]["stage"] = "modified"
        model._concepts["variables"]["p_mastery"] = 0.5
        result = model.process_event(_event(
            "code_modified", success=None, minute=1,
        ))
        # Stage should not change (already modified → modified from code_modified).
        # p_mastery should not change (success=None).
        assert result is None


# ── Concept detection helper ──────────────────────────────────────────────────

class TestDetectConcepts:
    """Test the _detect_concepts_in_code helper directly."""

    def test_empty_code(self) -> None:
        assert _detect_concepts_in_code("") == set()

    def test_import_only(self) -> None:
        # ImportFrom doesn't map to any concept.
        concepts = _detect_concepts_in_code("from golem import *\n")
        # No tracked concepts from just an import.
        assert "variables" not in concepts

    def test_sdk_pattern_1(self) -> None:
        """GOLEM_SDK.md Pattern 1: Simple Action."""
        code = '''\
from golem import *

player_pos = get_player_position("Alex")
move_to(player_pos.x, player_pos.y, player_pos.z)
say("I'm here!")
'''
        concepts = _detect_concepts_in_code(code)
        assert "variables" in concepts
        assert "function_calls" in concepts
        assert "attribute_access" in concepts

    def test_sdk_pattern_2(self) -> None:
        """GOLEM_SDK.md Pattern 2: Variables as Knobs."""
        code = '''\
from golem import *

pos = get_position()
block = "cobblestone"
place_block(pos.x + 1, pos.y, pos.z, block)
place_block(pos.x + 2, pos.y, pos.z, block)
'''
        concepts = _detect_concepts_in_code(code)
        assert "variables" in concepts
        assert "function_calls" in concepts
        assert "attribute_access" in concepts
        assert "arithmetic" in concepts

    def test_not_operator_detected_as_boolean_logic(self) -> None:
        code = 'x = not True\n'
        concepts = _detect_concepts_in_code(code)
        assert "boolean_logic" in concepts

    def test_subscript_detected_as_lists(self) -> None:
        code = 'x = items[0]\n'
        concepts = _detect_concepts_in_code(code)
        assert "lists" in concepts
