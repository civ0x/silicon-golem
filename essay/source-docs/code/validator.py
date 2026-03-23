"""AST allowlist enforcement for Silicon Golem.

Takes a Python source string and a concept level. Parses to AST, walks every
node, rejects anything not in the permitted set. Returns structured errors
for consumption by the chat agent's error translation layer.

Uses only the ast stdlib module. Zero external dependencies.
"""

import ast
import re
from dataclasses import dataclass, field


@dataclass
class ValidationError:
    """A single validation failure."""
    line: int
    construct: str
    message: str


@dataclass
class ValidationResult:
    """Result of validating a source string against a concept level."""
    valid: bool
    errors: list[ValidationError] = field(default_factory=list)


# AST context nodes that are structural infrastructure, not user-facing concepts.
# These always accompany Name/Attribute nodes and carry no pedagogical weight.
_STRUCTURAL_NODES = frozenset({"Load", "Store"})

# Compound statement types that increase nesting depth.
_COMPOUND_NODES = frozenset({
    "For", "While", "If", "With", "FunctionDef",
    "AsyncFor", "AsyncWith", "Try", "ExceptHandler",
})

# ---------------------------------------------------------------------------
# Level configurations
#
# Level 1: fully specified by the concept allowlist in GOLEM_SDK.md.
# Levels 2-3: derived from the preview sections in GOLEM_SDK.md.
# ---------------------------------------------------------------------------

_LEVEL_1_SDK_FUNCTIONS = frozenset({
    "move_to", "move_to_player", "place_block", "dig_block", "dig_area",
    "craft", "give", "equip", "get_position", "get_player_position",
    "find_blocks", "find_player", "get_inventory", "get_block", "say",
    "collect", "build_line", "build_wall",
})

LEVEL_CONFIGS: dict[int, dict] = {
    1: {
        "permitted_nodes": frozenset({
            # Statements
            "Module", "Assign", "Expr",
            # Expressions
            "Call", "Name", "Constant", "Attribute", "BinOp", "UnaryOp",
            # Binary operators
            "Add", "Sub", "Mult",
            # Unary operators (negative coordinates are common in Minecraft)
            "USub",
            # Other
            "arguments", "arg", "keyword", "ImportFrom", "alias",
        }),
        "permitted_sdk_functions": _LEVEL_1_SDK_FUNCTIONS,
        "permitted_builtins": frozenset({"print", "int", "str", "len"}),
        "max_nesting_depth": 1,
        "max_lines": 40,
        "max_variables": 10,
        "max_repeated_similar_lines": 8,
    },
    2: {
        "permitted_nodes": frozenset({
            # Level 1 nodes
            "Module", "Assign", "Expr",
            "Call", "Name", "Constant", "Attribute", "BinOp", "UnaryOp",
            "Add", "Sub", "Mult", "USub",
            "arguments", "arg", "keyword", "ImportFrom", "alias",
            # Level 2 additions: loops, conditionals, comparisons
            "For", "If", "IfExp",
            "Compare", "Eq", "NotEq", "Lt", "Gt", "LtE", "GtE",
            "BoolOp", "And", "Or",
            "Not",
        }),
        "permitted_sdk_functions": _LEVEL_1_SDK_FUNCTIONS,
        "permitted_builtins": frozenset({
            "print", "int", "str", "len", "range", "bool",
        }),
        "max_nesting_depth": 2,
        "max_lines": 60,
        "max_variables": 15,
        "max_repeated_similar_lines": 4,
    },
    3: {
        "permitted_nodes": frozenset({
            # Level 1+2 nodes
            "Module", "Assign", "Expr",
            "Call", "Name", "Constant", "Attribute", "BinOp", "UnaryOp",
            "Add", "Sub", "Mult", "USub",
            "arguments", "arg", "keyword", "ImportFrom", "alias",
            "For", "If", "IfExp",
            "Compare", "Eq", "NotEq", "Lt", "Gt", "LtE", "GtE",
            "BoolOp", "And", "Or", "Not",
            # Level 3 additions: function definitions
            "FunctionDef", "Return",
        }),
        "permitted_sdk_functions": _LEVEL_1_SDK_FUNCTIONS,
        "permitted_builtins": frozenset({
            "print", "int", "str", "len", "range", "bool",
        }),
        "max_nesting_depth": 3,
        "max_lines": 80,
        "max_variables": 20,
        "max_repeated_similar_lines": 4,
    },
}


def validate(source: str, level: int = 1) -> ValidationResult:
    """Validate a Python source string against a concept level.

    Args:
        source: Python source code to validate.
        level: Concept level (1, 2, or 3).

    Returns:
        ValidationResult with valid=True if the code passes, or a list of
        structured errors describing every violation found.
    """
    config = LEVEL_CONFIGS.get(level)
    if config is None:
        return ValidationResult(
            valid=False,
            errors=[ValidationError(
                line=0, construct="level",
                message=f"Unknown concept level: {level}",
            )],
        )

    errors: list[ValidationError] = []

    # --- Line count ---
    lines = source.split("\n")
    code_lines = [l for l in lines if l.strip() and not l.strip().startswith("#")]
    if len(code_lines) > config["max_lines"]:
        errors.append(ValidationError(
            line=0, construct="line_count",
            message=(
                f"Code has {len(code_lines)} lines, "
                f"maximum is {config['max_lines']}"
            ),
        ))

    # --- Parse ---
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        errors.append(ValidationError(
            line=e.lineno or 0, construct="syntax",
            message=f"Python syntax error: {e.msg}",
        ))
        return ValidationResult(valid=False, errors=errors)

    permitted = config["permitted_nodes"] | _STRUCTURAL_NODES
    sdk_funcs = config["permitted_sdk_functions"]
    builtins_ = config["permitted_builtins"]

    # Collect user-defined function names so calls to them are allowed (Level 3+).
    defined_functions: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            defined_functions.add(node.name)

    variables: set[str] = set()

    for node in ast.walk(tree):
        node_type = type(node).__name__

        # --- Node type allowlist ---
        if node_type not in permitted:
            errors.append(ValidationError(
                line=getattr(node, "lineno", 0), construct=node_type,
                message=f"'{node_type}' is not available at concept level {level}",
            ))
            continue

        # --- Import restrictions ---
        if isinstance(node, ast.ImportFrom):
            if (
                node.module != "golem"
                or len(node.names) != 1
                or node.names[0].name != "*"
            ):
                errors.append(ValidationError(
                    line=node.lineno, construct="ImportFrom",
                    message="Only 'from golem import *' is permitted",
                ))

        # --- Track variables for count check ---
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    variables.add(target.id)

        # --- Function call validation ---
        if isinstance(node, ast.Call):
            func_name = _get_call_name(node)
            if func_name is not None and func_name not in (
                sdk_funcs | builtins_ | defined_functions
            ):
                errors.append(ValidationError(
                    line=node.lineno, construct="Call",
                    message=(
                        f"Function '{func_name}' is not available "
                        f"at concept level {level}"
                    ),
                ))

    # --- Variable count ---
    if len(variables) > config["max_variables"]:
        errors.append(ValidationError(
            line=0, construct="variable_count",
            message=(
                f"Code uses {len(variables)} variables, "
                f"maximum is {config['max_variables']}"
            ),
        ))

    # --- Nesting depth ---
    max_depth = _max_nesting_depth(tree)
    if max_depth > config["max_nesting_depth"]:
        errors.append(ValidationError(
            line=0, construct="nesting_depth",
            message=(
                f"Code nesting depth is {max_depth}, "
                f"maximum is {config['max_nesting_depth']}"
            ),
        ))

    # --- Repeated similar lines ---
    max_repeated = _max_repeated_similar(source)
    if max_repeated > config["max_repeated_similar_lines"]:
        errors.append(ValidationError(
            line=0, construct="repeated_lines",
            message=(
                f"Code has {max_repeated} near-identical lines, "
                f"maximum is {config['max_repeated_similar_lines']}"
            ),
        ))

    return ValidationResult(valid=len(errors) == 0, errors=errors)


def _get_call_name(node: ast.Call) -> str | None:
    """Extract function name from a Call node.

    Returns the name for simple calls (``func(...)``). Returns None for
    attribute calls (``obj.method(...)``), which are not SDK/builtin
    calls and don't need function-name validation.
    """
    if isinstance(node.func, ast.Name):
        return node.func.id
    return None


def _max_nesting_depth(tree: ast.AST) -> int:
    """Calculate the maximum nesting depth of compound statements."""
    def _depth(node: ast.AST, current: int) -> int:
        deepest = current
        for child in ast.iter_child_nodes(node):
            if type(child).__name__ in _COMPOUND_NODES:
                deepest = max(deepest, _depth(child, current + 1))
            else:
                deepest = max(deepest, _depth(child, current))
        return deepest
    return _depth(tree, 0)


_RE_STRING = re.compile(r"""(?:"[^"]*"|'[^']*')""")
_RE_NUMBER = re.compile(r"\b\d+\b")


def _normalize_line(line: str) -> str:
    """Normalize a source line for similarity comparison.

    Replaces string literals and integer literals with placeholders so that
    lines differing only in literal values compare as equal.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return ""
    normalized = _RE_STRING.sub('"_"', stripped)
    normalized = _RE_NUMBER.sub("N", normalized)
    return normalized


def _max_repeated_similar(source: str) -> int:
    """Return the length of the longest run of consecutive near-identical lines.

    Comments and blank lines are filtered out before comparison.
    """
    normalized = [_normalize_line(l) for l in source.split("\n")]
    normalized = [n for n in normalized if n]
    if not normalized:
        return 0

    max_run = 1
    current_run = 1
    for i in range(1, len(normalized)):
        if normalized[i] == normalized[i - 1]:
            current_run += 1
            if current_run > max_run:
                max_run = current_run
        else:
            current_run = 1
    return max_run
