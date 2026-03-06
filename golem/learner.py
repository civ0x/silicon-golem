"""Learner model for Silicon Golem.

Tracks per-concept mastery using Bayesian Knowledge Tracing (BKT) and
a seven-stage progression model. Synchronous, <100ms per operation.

Uses only stdlib: ast, json, dataclasses, datetime, pathlib.
"""

import ast
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ── Concept Registry ─────────────────────────────────────────────────────────

CONCEPT_REGISTRY: dict[str, dict[str, Any]] = {
    "variables": {
        "level_gate": 1,
        "prerequisites": [],
    },
    "function_calls": {
        "level_gate": 1,
        "prerequisites": [],
    },
    "attribute_access": {
        "level_gate": 1,
        "prerequisites": ["variables"],
    },
    "arithmetic": {
        "level_gate": 1,
        "prerequisites": ["variables"],
    },
    "string_concatenation": {
        "level_gate": 1,
        "prerequisites": ["variables"],
    },
    "for_loops": {
        "level_gate": 2,
        "prerequisites": ["variables"],
    },
    "conditionals": {
        "level_gate": 2,
        "prerequisites": ["variables"],
    },
    "comparison_operators": {
        "level_gate": 2,
        "prerequisites": ["conditionals"],
    },
    "boolean_logic": {
        "level_gate": 2,
        "prerequisites": ["conditionals"],
    },
    "function_definitions": {
        "level_gate": 3,
        "prerequisites": ["for_loops", "conditionals"],
    },
    "return_values": {
        "level_gate": 3,
        "prerequisites": ["function_definitions"],
    },
    "lists": {
        "level_gate": 4,
        "prerequisites": ["for_loops"],
    },
    "dictionaries": {
        "level_gate": 4,
        "prerequisites": ["lists"],
    },
    "while_loops": {
        "level_gate": 5,
        "prerequisites": ["for_loops", "conditionals"],
    },
    "string_formatting": {
        "level_gate": 5,
        "prerequisites": ["variables", "string_concatenation"],
    },
}

# BKT learn rates per concept.
LEARN_RATES: dict[str, float] = {
    "variables": 0.30,
    "function_calls": 0.25,
    "attribute_access": 0.25,
    "arithmetic": 0.20,
    "string_concatenation": 0.15,
    "for_loops": 0.15,
    "conditionals": 0.15,
    "comparison_operators": 0.20,
    "boolean_logic": 0.12,
    "function_definitions": 0.10,
    "return_values": 0.10,
    "lists": 0.12,
    "dictionaries": 0.10,
    "while_loops": 0.10,
    "string_formatting": 0.20,
}

# BKT global parameters.
P_SLIP = 0.10
P_GUESS = 0.20

# Mastery thresholds.
MASTERY_THRESHOLDS = {
    "stage_advance_minimum": 0.70,
    "challenge_targeting": 0.50,
    "level_gate_promotion": 0.85,
    "composed_prerequisite": 0.90,
}

# Ordered stages (index = rank for comparison).
STAGES = ("none", "exposed", "read", "modified", "authored", "debugged", "composed")
_STAGE_INDEX = {s: i for i, s in enumerate(STAGES)}

# Concept-to-AST-node mapping.
# "BinOp_with_str" is a pseudo-marker handled specially in detection.
CONCEPT_AST_MAPPING: dict[str, list[str]] = {
    "variables": ["Assign"],
    "function_calls": ["Call"],
    "attribute_access": ["Attribute"],
    "arithmetic": ["BinOp", "Add", "Sub", "Mult"],
    "string_concatenation": ["BinOp_with_str"],
    "for_loops": ["For"],
    "conditionals": ["If", "IfExp"],
    "comparison_operators": ["Compare", "Eq", "NotEq", "Lt", "Gt", "LtE", "GtE"],
    "boolean_logic": ["BoolOp", "And", "Or", "Not"],
    "function_definitions": ["FunctionDef"],
    "return_values": ["Return"],
    "lists": ["List", "Subscript"],
    "dictionaries": ["Dict"],
    "while_loops": ["While"],
    "string_formatting": ["JoinedStr", "FormattedValue"],
}

# Events that produce BKT observations (with success=True/False).
_BKT_EVENTS = frozenset({
    "code_modified", "code_authored", "code_debugged",
    "error_encountered", "concept_used",
})

# Events that can advance stage but don't produce BKT observations.
_STAGE_ONLY_EVENTS = frozenset({
    "code_inspected", "code_read", "concept_asked",
})

# Map from event type to the stage it can transition TO.
_EVENT_TO_TARGET_STAGE: dict[str, str] = {
    "code_inspected": "read",
    "code_read": "read",
    "concept_asked": "read",
    "code_modified": "modified",
    "code_authored": "authored",
    "code_debugged": "debugged",
    "concept_used": "composed",
}


# ── Data Types ────────────────────────────────────────────────────────────────

@dataclass
class LearnerEvent:
    """An event from the chat agent, enriched by the orchestrator."""
    event: str
    concept: str | None
    detail: str
    context: str
    success: bool | None
    timestamp: datetime


@dataclass
class StateChange:
    """Describes what changed after processing an event."""
    concept: str
    old_stage: str
    new_stage: str
    old_p_mastery: float
    new_p_mastery: float
    stage_changed: bool = field(init=False)

    def __post_init__(self) -> None:
        self.stage_changed = self.old_stage != self.new_stage


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _default_concept_state() -> dict[str, Any]:
    return {
        "stage": "none",
        "p_mastery": 0.0,
        "contexts_seen": [],
        "total_observations": 0,
        "correct_observations": 0,
        "last_observation_timestamp": None,
        "stage_history": [],
    }


def _bkt_update(p_mastery: float, correct: bool, p_learn: float) -> float:
    """Standard BKT forward algorithm update."""
    if correct:
        p_ln = (p_mastery * (1 - P_SLIP)) / (
            p_mastery * (1 - P_SLIP) + (1 - p_mastery) * P_GUESS
        )
    else:
        p_ln = (p_mastery * P_SLIP) / (
            p_mastery * P_SLIP + (1 - p_mastery) * (1 - P_GUESS)
        )
    # Apply learn rate.
    p_ln = p_ln + (1 - p_ln) * p_learn
    return p_ln


def _detect_concepts_in_code(code: str) -> set[str]:
    """Parse Python code and return the set of concepts present in the AST."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return set()

    found_node_types: set[str] = set()
    has_string_binop = False

    for node in ast.walk(tree):
        node_type = type(node).__name__
        found_node_types.add(node_type)

        # Detect string concatenation: BinOp where either operand is a string
        # literal or a str() call.
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            if _operand_is_stringy(node.left) or _operand_is_stringy(node.right):
                has_string_binop = True

    concepts: set[str] = set()
    for concept, ast_nodes in CONCEPT_AST_MAPPING.items():
        for ast_node in ast_nodes:
            if ast_node == "BinOp_with_str":
                if has_string_binop:
                    concepts.add(concept)
            elif ast_node in found_node_types:
                concepts.add(concept)
                break

    # If we found string_concatenation via BinOp_with_str, and arithmetic is
    # only present because of BinOp (not Add/Sub/Mult on numbers), we need
    # to be careful. But the mapping for arithmetic includes BinOp, Add, Sub,
    # Mult — if any of those appear, arithmetic is detected. This is acceptable:
    # a BinOp with Add on strings still uses Add node. The heuristic is that
    # if there's *any* BinOp, arithmetic is present unless all BinOps are
    # string concatenation. For v1, we accept the overlap — both concepts
    # get detected if a string concat uses +.

    return concepts


def _operand_is_stringy(node: ast.expr) -> bool:
    """Check if an AST expression is a string literal or str() call."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return True
    if (isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "str"):
        return True
    return False


# ── LearnerModel ──────────────────────────────────────────────────────────────

class LearnerModel:
    """Tracks kid's concept mastery. Synchronous, <100ms per operation."""

    def __init__(self, player_name: str, state_path: str = "data/learner_state.json") -> None:
        """Load or create learner state for the given player."""
        self._path = Path(state_path)
        self._player_name = player_name

        if self._path.exists():
            with open(self._path) as f:
                data = json.load(f)
            self._load_from_dict(data)
        else:
            self._concepts: dict[str, dict[str, Any]] = {}
            for concept in CONCEPT_REGISTRY:
                self._concepts[concept] = _default_concept_state()
            self._session_signals: dict[str, Any] = {"disengagement_events": []}
            self._session_history: dict[str, Any] = {
                "total_sessions": 0,
                "total_play_minutes": 0,
                "concepts_introduced_per_session": [],
            }
            self._created = _now().isoformat()
            self._last_updated = self._created

    def _load_from_dict(self, data: dict[str, Any]) -> None:
        self._concepts = {}
        for concept in CONCEPT_REGISTRY:
            if concept in data.get("concepts", {}):
                self._concepts[concept] = data["concepts"][concept]
            else:
                self._concepts[concept] = _default_concept_state()
        self._session_signals = data.get("session_signals", {"disengagement_events": []})
        self._session_history = data.get("session_history", {
            "total_sessions": 0,
            "total_play_minutes": 0,
            "concepts_introduced_per_session": [],
        })
        self._created = data.get("created", _now().isoformat())
        self._last_updated = data.get("last_updated", _now().isoformat())

    def process_event(self, event: LearnerEvent) -> StateChange | None:
        """Process a learner model event. Returns StateChange if state changed."""
        # Handle disengagement — session-level signal, no BKT effect.
        if event.event == "disengaged":
            self._session_signals["disengagement_events"].append({
                "timestamp": event.timestamp.isoformat(),
                "detail": event.detail,
                "active_challenge_id": None,
                "current_activity": event.context,
            })
            self._last_updated = event.timestamp.isoformat()
            return None

        # Events with no concept don't affect concept state.
        if event.concept is None:
            return None

        # Unknown concept — ignore.
        if event.concept not in CONCEPT_REGISTRY:
            return None

        state = self._concepts[event.concept]
        old_stage = state["stage"]
        old_p_mastery = state["p_mastery"]

        # Stage transition.
        target_stage = _EVENT_TO_TARGET_STAGE.get(event.event)
        if target_stage is not None:
            self._advance_stage(event.concept, target_stage, event.timestamp)

        # BKT update.
        if event.event in _BKT_EVENTS and event.success is not None:
            p_learn = LEARN_RATES[event.concept]
            state["p_mastery"] = _bkt_update(state["p_mastery"], event.success, p_learn)
            state["total_observations"] += 1
            if event.success:
                state["correct_observations"] += 1
            state["last_observation_timestamp"] = event.timestamp.isoformat()

        # Context tracking.
        if event.context and event.context not in state["contexts_seen"]:
            state["contexts_seen"].append(event.context)

        self._last_updated = event.timestamp.isoformat()

        new_stage = state["stage"]
        new_p_mastery = state["p_mastery"]

        if new_stage != old_stage or abs(new_p_mastery - old_p_mastery) > 1e-9:
            return StateChange(
                concept=event.concept,
                old_stage=old_stage,
                new_stage=new_stage,
                old_p_mastery=old_p_mastery,
                new_p_mastery=new_p_mastery,
            )
        return None

    def _advance_stage(self, concept: str, target: str, timestamp: datetime) -> None:
        """Advance a concept's stage, allowing skip-forward but never backward."""
        state = self._concepts[concept]
        current_idx = _STAGE_INDEX[state["stage"]]
        target_idx = _STAGE_INDEX[target]

        # composed can only be reached from authored or debugged.
        if target == "composed" and current_idx < _STAGE_INDEX["authored"]:
            return

        if target_idx > current_idx:
            state["stage"] = target
            state["stage_history"].append({
                "stage": target,
                "timestamp": timestamp.isoformat(),
            })

    def process_code_displayed(self, code: str) -> list[str]:
        """Identify concepts in displayed code. Advance 'none' → 'exposed'.

        Returns list of newly exposed concept names.
        """
        concepts = _detect_concepts_in_code(code)
        newly_exposed: list[str] = []
        now = _now()

        for concept in concepts:
            if concept not in self._concepts:
                continue
            if self._concepts[concept]["stage"] == "none":
                self._advance_stage(concept, "exposed", now)
                newly_exposed.append(concept)

        if newly_exposed:
            self._last_updated = now.isoformat()

        return newly_exposed

    def get_agent_state(self) -> dict[str, Any]:
        """Trimmed state for agent context injection."""
        concepts_trimmed: dict[str, Any] = {}
        for concept, state in self._concepts.items():
            concepts_trimmed[concept] = {
                "stage": state["stage"],
                "p_mastery": round(state["p_mastery"], 4),
                "contexts_seen": state["contexts_seen"],
            }
        return {
            "current_level": self.get_current_level(),
            "concepts": concepts_trimmed,
        }

    def get_concept_readiness(self) -> dict[str, Any]:
        """Readiness assessment for the challenge agent."""
        ready_to_introduce: list[dict[str, Any]] = []
        ready_to_advance: list[dict[str, Any]] = []
        prerequisites_not_met: list[dict[str, Any]] = []

        for concept, registry in CONCEPT_REGISTRY.items():
            state = self._concepts[concept]

            if state["stage"] == "none":
                # Check if prerequisites are met for introduction.
                prereqs = registry["prerequisites"]
                prereqs_met = True
                missing: list[str] = []
                for prereq in prereqs:
                    prereq_state = self._concepts[prereq]
                    prereq_idx = _STAGE_INDEX[prereq_state["stage"]]
                    if (prereq_idx < _STAGE_INDEX["modified"]
                            or prereq_state["p_mastery"] < MASTERY_THRESHOLDS["stage_advance_minimum"]):
                        prereqs_met = False
                        missing.append(prereq)

                if prereqs_met:
                    ready_to_introduce.append({
                        "concept": concept,
                        "level_gate": registry["level_gate"],
                    })
                elif prereqs:
                    prerequisites_not_met.append({
                        "concept": concept,
                        "missing_prerequisites": missing,
                    })

            elif state["stage"] not in ("none", "composed"):
                ready_to_advance.append({
                    "concept": concept,
                    "current_stage": state["stage"],
                    "p_mastery": round(state["p_mastery"], 4),
                    "contexts_seen": state["contexts_seen"],
                })

        return {
            "ready_to_introduce": ready_to_introduce,
            "ready_to_advance": ready_to_advance,
            "prerequisites_not_met": prerequisites_not_met,
        }

    def get_current_level(self) -> int:
        """Returns the kid's current concept level (1-5+)."""
        # Find the highest level L such that all concepts with level_gate <= L-1
        # are at stage >= modified with p_mastery >= level_gate_promotion.
        max_level = max(r["level_gate"] for r in CONCEPT_REGISTRY.values())

        for level in range(max_level, 1, -1):
            all_met = True
            for concept, registry in CONCEPT_REGISTRY.items():
                if registry["level_gate"] <= level - 1:
                    state = self._concepts[concept]
                    stage_idx = _STAGE_INDEX[state["stage"]]
                    if (stage_idx < _STAGE_INDEX["modified"]
                            or state["p_mastery"] < MASTERY_THRESHOLDS["level_gate_promotion"]):
                        all_met = False
                        break
            if all_met:
                return level

        return 1

    def save(self) -> None:
        """Persist state to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 1,
            "player_name": self._player_name,
            "created": self._created,
            "last_updated": self._last_updated,
            "current_level": self.get_current_level(),
            "concepts": self._concepts,
            "session_signals": self._session_signals,
            "session_history": self._session_history,
        }
        with open(self._path, "w") as f:
            json.dump(data, f, indent=2)
