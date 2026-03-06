"""Tests for the AST allowlist validator.

Organized by the test strategy from HANDOFF.md:
1. Level 1 code patterns from GOLEM_SDK.md pass at Level 1
2. Level 2 code patterns fail at Level 1, pass at Level 2
3. Level 3 code patterns fail at Level 2, pass at Level 3
4. Import validation
5. Function call validation
6. Nesting depth
7. Line count
8. Variable count
9. Repeated similar lines
10. Edge cases
"""

import pytest

from golem.validator import validate, ValidationResult


# ── Helpers ──────────────────────────────────────────────────────────────────

def assert_valid(result: ValidationResult) -> None:
    assert result.valid, f"Expected valid, got errors: {result.errors}"


def assert_invalid(result: ValidationResult, construct: str | None = None) -> None:
    assert not result.valid, "Expected invalid, got valid"
    if construct is not None:
        constructs = [e.construct for e in result.errors]
        assert construct in constructs, (
            f"Expected error for '{construct}', got: {constructs}"
        )


# ── 1. Level 1 code patterns (GOLEM_SDK.md) ─────────────────────────────────

class TestLevel1Patterns:
    """All code patterns from GOLEM_SDK.md should pass validation at Level 1."""

    def test_pattern1_simple_action(self) -> None:
        code = '''\
from golem import *

player_pos = get_player_position("Alex")
move_to(player_pos.x, player_pos.y, player_pos.z)
say("I'm here! What do you need?")
'''
        assert_valid(validate(code, level=1))

    def test_pattern2_variables_as_knobs(self) -> None:
        code = '''\
from golem import *

pos = get_position()
block = "cobblestone"
length = 5

place_block(pos.x + 1, pos.y, pos.z, block)
place_block(pos.x + 2, pos.y, pos.z, block)
place_block(pos.x + 3, pos.y, pos.z, block)
place_block(pos.x + 4, pos.y, pos.z, block)
place_block(pos.x + 5, pos.y, pos.z, block)
'''
        assert_valid(validate(code, level=1))

    def test_pattern2_compound_variant(self) -> None:
        code = '''\
from golem import *

pos = get_position()
build_wall(pos.x + 1, pos.y, pos.z, "east", 5, 1, "cobblestone")
'''
        assert_valid(validate(code, level=1))

    def test_pattern3_observation_and_action(self) -> None:
        code = '''\
from golem import *

pos = get_position()
ground = get_block(pos.x, pos.y - 1, pos.z)
front = get_block(pos.x + 1, pos.y, pos.z)
above = get_block(pos.x, pos.y + 2, pos.z)

say("You're standing on " + ground)
say("In front of you: " + front)
say("Above you: " + above)
'''
        assert_valid(validate(code, level=1))

    def test_pattern4_multi_step_task(self) -> None:
        code = '''\
from golem import *

collected = collect("oak_log", 10)
say("Got " + str(collected) + " oak logs!")

craft("oak_planks", 10)
pos = get_player_position("Alex")

x = pos.x + 1
y = pos.y - 1
z = pos.z + 1

place_block(x, y, z, "oak_planks")
place_block(x + 1, y, z, "oak_planks")
place_block(x + 2, y, z, "oak_planks")
place_block(x, y, z + 1, "oak_planks")
place_block(x + 1, y, z + 1, "oak_planks")
place_block(x + 2, y, z + 1, "oak_planks")
place_block(x, y, z + 2, "oak_planks")
place_block(x + 1, y, z + 2, "oak_planks")
place_block(x + 2, y, z + 2, "oak_planks")
'''
        assert_valid(validate(code, level=1))

    def test_challenge_walkthrough_floor(self) -> None:
        """The 5x5 floor from the full challenge walkthrough in GOLEM_SDK.md."""
        code = '''\
from golem import *

pos = get_player_position("Alex")
block = "oak_planks"

x = pos.x - 2
y = pos.y - 1
z = pos.z - 2

place_block(x, y, z, block)
place_block(x + 1, y, z, block)
place_block(x + 2, y, z, block)
place_block(x + 3, y, z, block)
place_block(x + 4, y, z, block)

place_block(x, y, z + 1, block)
place_block(x + 1, y, z + 1, block)
place_block(x + 2, y, z + 1, block)
place_block(x + 3, y, z + 1, block)
place_block(x + 4, y, z + 1, block)

place_block(x, y, z + 2, block)
place_block(x + 1, y, z + 2, block)
place_block(x + 2, y, z + 2, block)
place_block(x + 3, y, z + 2, block)
place_block(x + 4, y, z + 2, block)

place_block(x, y, z + 3, block)
place_block(x + 1, y, z + 3, block)
place_block(x + 2, y, z + 3, block)
place_block(x + 3, y, z + 3, block)
place_block(x + 4, y, z + 3, block)

place_block(x, y, z + 4, block)
place_block(x + 1, y, z + 4, block)
place_block(x + 2, y, z + 4, block)
place_block(x + 3, y, z + 4, block)
place_block(x + 4, y, z + 4, block)
'''
        assert_valid(validate(code, level=1))

    def test_all_sdk_functions_callable(self) -> None:
        """Every Level 1 SDK function is accepted as a bare call."""
        funcs = [
            'move_to(1, 64, 1)',
            'move_to_player("Alex")',
            'place_block(1, 64, 1, "stone")',
            'dig_block(1, 64, 1)',
            'dig_area(0, 60, 0, 5, 65, 5)',
            'craft("iron_pickaxe")',
            'give("cobblestone", count=10)',
            'equip("diamond_sword")',
            'pos = get_position()',
            'pos = get_player_position("Alex")',
            'blocks = find_blocks("diamond_ore")',
            'pos = find_player("Alex")',
            'inv = get_inventory()',
            'b = get_block(1, 64, 1)',
            'say("hello")',
            'n = collect("oak_log", 10)',
            'build_line(0, 64, 0, "east", 5, "stone")',
            'build_wall(0, 64, 0, "north", 10, 3, "cobblestone")',
        ]
        code = "from golem import *\n" + "\n".join(funcs)
        assert_valid(validate(code, level=1))

    def test_permitted_builtins(self) -> None:
        code = '''\
from golem import *

x = int("5")
name = str(42)
n = len("hello")
print("debug")
'''
        assert_valid(validate(code, level=1))

    def test_unary_minus(self) -> None:
        """Negative coordinates are common in Minecraft."""
        code = '''\
from golem import *

move_to(-100, 64, -200)
'''
        assert_valid(validate(code, level=1))

    def test_arithmetic_operations(self) -> None:
        code = '''\
from golem import *

pos = get_position()
x = pos.x + 1
y = pos.y - 1
z = pos.z * 2
'''
        assert_valid(validate(code, level=1))


# ── 2. Level 2 patterns: fail at L1, pass at L2 ────────────────────────────

class TestLevel2Patterns:

    def test_for_loop_passes_level2(self) -> None:
        code = '''\
from golem import *

pos = get_position()
block = "cobblestone"
length = 10

for i in range(length):
    place_block(pos.x + i, pos.y, pos.z, block)
'''
        assert_valid(validate(code, level=2))

    def test_for_loop_fails_level1(self) -> None:
        code = '''\
from golem import *

for i in range(10):
    place_block(i, 64, 0, "stone")
'''
        assert_invalid(validate(code, level=1), construct="For")

    def test_if_conditional_passes_level2(self) -> None:
        code = '''\
from golem import *

block = get_block(0, 64, 0)
if block == "air":
    place_block(0, 64, 0, "cobblestone")
'''
        assert_valid(validate(code, level=2))

    def test_if_conditional_fails_level1(self) -> None:
        code = '''\
from golem import *

block = get_block(0, 64, 0)
if block == "air":
    place_block(0, 64, 0, "cobblestone")
'''
        assert_invalid(validate(code, level=1), construct="If")

    def test_comparison_operators(self) -> None:
        code = '''\
from golem import *

pos = get_position()
if pos.y > 64:
    say("high up")
if pos.y < 10:
    say("deep underground")
if pos.y == 64:
    say("sea level")
if pos.y != 0:
    say("not at bedrock")
'''
        assert_valid(validate(code, level=2))

    def test_boolean_operators(self) -> None:
        code = '''\
from golem import *

pos = get_position()
if pos.x > 0 and pos.z > 0:
    say("northeast quadrant")
if pos.x < 0 or pos.z < 0:
    say("might be southwest")
'''
        assert_valid(validate(code, level=2))

    def test_range_builtin_level2(self) -> None:
        code = '''\
from golem import *

for i in range(5):
    say(str(i))
'''
        assert_valid(validate(code, level=2))

    def test_range_fails_level1(self) -> None:
        """range() is not in Level 1 builtins (and For isn't allowed either)."""
        # Even though For would be caught first, range alone in a Call is also invalid.
        code = '''\
from golem import *

x = range(10)
'''
        assert_invalid(validate(code, level=1), construct="Call")


# ── 3. Level 3 patterns: fail at L2, pass at L3 ────────────────────────────

class TestLevel3Patterns:

    def test_function_def_passes_level3(self) -> None:
        code = '''\
from golem import *

def build_tower(x, y, z, height, block):
    for i in range(height):
        place_block(x, y + i, z, block)

build_tower(10, 64, 20, 8, "cobblestone")
build_tower(15, 64, 20, 12, "stone_bricks")
build_tower(20, 64, 20, 6, "oak_planks")
'''
        assert_valid(validate(code, level=3))

    def test_function_def_fails_level2(self) -> None:
        code = '''\
from golem import *

def build_tower(x, y, z, height, block):
    for i in range(height):
        place_block(x, y + i, z, block)

build_tower(10, 64, 20, 8, "cobblestone")
'''
        assert_invalid(validate(code, level=2), construct="FunctionDef")

    def test_function_def_fails_level1(self) -> None:
        code = '''\
from golem import *

def greet():
    say("hello")

greet()
'''
        assert_invalid(validate(code, level=1), construct="FunctionDef")

    def test_return_statement_passes_level3(self) -> None:
        code = '''\
from golem import *

def count_blocks(block_type):
    blocks = find_blocks(block_type)
    return len(blocks)

n = count_blocks("diamond_ore")
say("Found " + str(n) + " diamonds nearby")
'''
        assert_valid(validate(code, level=3))

    def test_return_fails_level2(self) -> None:
        code = '''\
from golem import *

def get_height():
    return 5
'''
        # FunctionDef fails before Return, but Return is also not permitted
        assert_invalid(validate(code, level=2))

    def test_user_defined_function_calls(self) -> None:
        """Calls to user-defined functions should be allowed at Level 3."""
        code = '''\
from golem import *

def my_func():
    say("hi")

my_func()
'''
        assert_valid(validate(code, level=3))


# ── 4. Import validation ────────────────────────────────────────────────────

class TestImportValidation:

    def test_golem_star_import_passes(self) -> None:
        code = 'from golem import *\nprint("hi")'
        assert_valid(validate(code, level=1))

    def test_bare_import_fails(self) -> None:
        code = 'import os'
        assert_invalid(validate(code, level=1), construct="Import")

    def test_import_from_other_module_fails(self) -> None:
        code = 'from os import path'
        assert_invalid(validate(code, level=1), construct="ImportFrom")

    def test_import_specific_from_golem_fails(self) -> None:
        """Only 'from golem import *' is permitted, not named imports."""
        code = 'from golem import place_block'
        assert_invalid(validate(code, level=1), construct="ImportFrom")

    def test_import_random_fails(self) -> None:
        code = 'import random'
        assert_invalid(validate(code, level=1), construct="Import")

    def test_import_from_math_fails(self) -> None:
        code = 'from math import sqrt'
        assert_invalid(validate(code, level=1), construct="ImportFrom")

    def test_multiple_imports_fail(self) -> None:
        code = '''\
from golem import *
import os
'''
        assert_invalid(validate(code, level=1), construct="Import")


# ── 5. Function call validation ─────────────────────────────────────────────

class TestFunctionCallValidation:

    def test_sdk_function_passes(self) -> None:
        code = '''\
from golem import *

place_block(1, 64, 1, "stone")
'''
        assert_valid(validate(code, level=1))

    def test_open_fails(self) -> None:
        code = '''\
from golem import *

f = open("test.txt")
'''
        assert_invalid(validate(code, level=1), construct="Call")

    def test_exec_fails(self) -> None:
        code = '''\
from golem import *

exec("print(1)")
'''
        assert_invalid(validate(code, level=1), construct="Call")

    def test_eval_fails(self) -> None:
        code = '''\
from golem import *

x = eval("1 + 1")
'''
        assert_invalid(validate(code, level=1), construct="Call")

    def test_input_fails(self) -> None:
        code = '''\
from golem import *

x = input("enter: ")
'''
        assert_invalid(validate(code, level=1), construct="Call")

    def test_unknown_function_fails(self) -> None:
        code = '''\
from golem import *

do_something_weird()
'''
        assert_invalid(validate(code, level=1), construct="Call")

    def test_attribute_calls_not_blocked(self) -> None:
        """Attribute-style calls (obj.method()) aren't subject to function
        name validation — they pass through. The AST node check handles
        whether Attribute is permitted at all."""
        # This would fail at runtime but the validator doesn't catch attribute calls
        # since they could be valid method calls on SDK return types.
        code = '''\
from golem import *

pos = get_position()
x = pos.x
'''
        assert_valid(validate(code, level=1))


# ── 6. Nesting depth ────────────────────────────────────────────────────────

class TestNestingDepth:

    def test_flat_code_passes_level1(self) -> None:
        code = '''\
from golem import *

x = 1
y = 2
say("hi")
'''
        assert_valid(validate(code, level=1))

    def test_single_for_passes_level2(self) -> None:
        code = '''\
from golem import *

for i in range(5):
    say(str(i))
'''
        assert_valid(validate(code, level=2))

    def test_nested_for_if_passes_level2(self) -> None:
        code = '''\
from golem import *

for i in range(5):
    if i > 2:
        say(str(i))
'''
        assert_valid(validate(code, level=2))

    def test_triple_nesting_fails_level2(self) -> None:
        code = '''\
from golem import *

for i in range(5):
    for j in range(5):
        if i > j:
            say("deep")
'''
        assert_invalid(validate(code, level=2), construct="nesting_depth")

    def test_function_with_loop_passes_level3(self) -> None:
        code = '''\
from golem import *

def build(n):
    for i in range(n):
        place_block(i, 64, 0, "stone")

build(5)
'''
        assert_valid(validate(code, level=3))

    def test_function_with_deep_nesting_passes_level3(self) -> None:
        code = '''\
from golem import *

def build(n):
    for i in range(n):
        if i > 2:
            say(str(i))

build(5)
'''
        assert_valid(validate(code, level=3))

    def test_quadruple_nesting_fails_level3(self) -> None:
        code = '''\
from golem import *

def outer():
    for i in range(5):
        for j in range(5):
            if i > j:
                say("too deep")

outer()
'''
        assert_invalid(validate(code, level=3), construct="nesting_depth")


# ── 7. Line count ───────────────────────────────────────────────────────────

class TestLineCount:

    def test_within_limit_passes(self) -> None:
        lines = ["from golem import *"] + [f'x{i} = {i}' for i in range(9)]
        code = "\n".join(lines)
        assert_valid(validate(code, level=1))

    def test_exceeds_limit_fails(self) -> None:
        # Level 1 max is 40 lines. Generate 41 code lines.
        lines = ["from golem import *"] + [f'say("{i}")' for i in range(40)]
        code = "\n".join(lines)
        assert_invalid(validate(code, level=1), construct="line_count")

    def test_comments_and_blanks_not_counted(self) -> None:
        lines = ["from golem import *"]
        lines += ["# this is a comment"] * 50
        lines += [""] * 50
        lines += ['say("hi")']
        code = "\n".join(lines)
        assert_valid(validate(code, level=1))


# ── 8. Variable count ───────────────────────────────────────────────────────

class TestVariableCount:

    def test_within_limit_passes(self) -> None:
        lines = ["from golem import *"]
        for i in range(10):
            lines.append(f"var{i} = {i}")
        code = "\n".join(lines)
        assert_valid(validate(code, level=1))

    def test_exceeds_limit_fails(self) -> None:
        lines = ["from golem import *"]
        for i in range(11):
            lines.append(f"var{i} = {i}")
        code = "\n".join(lines)
        assert_invalid(validate(code, level=1), construct="variable_count")

    def test_reassignment_same_var_not_counted_twice(self) -> None:
        code = '''\
from golem import *

x = 1
x = 2
x = 3
'''
        result = validate(code, level=1)
        assert_valid(result)


# ── 9. Repeated similar lines ───────────────────────────────────────────────

class TestRepeatedSimilarLines:

    def test_within_limit_passes(self) -> None:
        """8 similar lines should pass at Level 1 (limit is 8)."""
        lines = ["from golem import *", "pos = get_position()"]
        for i in range(8):
            lines.append(f'place_block(pos.x + {i}, pos.y, pos.z, "stone")')
        code = "\n".join(lines)
        assert_valid(validate(code, level=1))

    def test_exceeds_limit_fails(self) -> None:
        """9 consecutive similar lines should fail at Level 1."""
        lines = ["from golem import *", "pos = get_position()"]
        for i in range(9):
            lines.append(f'place_block(pos.x + {i}, pos.y, pos.z, "stone")')
        code = "\n".join(lines)
        assert_invalid(validate(code, level=1), construct="repeated_lines")

    def test_varied_lines_pass(self) -> None:
        """Lines that look different don't count as repeated."""
        code = '''\
from golem import *

pos = get_position()
move_to(pos.x, pos.y, pos.z)
say("arrived")
block = get_block(pos.x, pos.y - 1, pos.z)
say("standing on " + block)
'''
        assert_valid(validate(code, level=1))

    def test_5x5_floor_with_row_breaks(self) -> None:
        """The 5x5 floor pattern from GOLEM_SDK.md shouldn't exceed the limit.

        Each row has at most 4 identical normalized lines (x+N variants),
        and rows differ from each other (z vs z+N).
        """
        code = '''\
from golem import *

pos = get_player_position("Alex")
block = "oak_planks"
x = pos.x - 2
y = pos.y - 1
z = pos.z - 2

place_block(x, y, z, block)
place_block(x + 1, y, z, block)
place_block(x + 2, y, z, block)
place_block(x + 3, y, z, block)
place_block(x + 4, y, z, block)
place_block(x, y, z + 1, block)
place_block(x + 1, y, z + 1, block)
place_block(x + 2, y, z + 1, block)
place_block(x + 3, y, z + 1, block)
place_block(x + 4, y, z + 1, block)
place_block(x, y, z + 2, block)
place_block(x + 1, y, z + 2, block)
place_block(x + 2, y, z + 2, block)
place_block(x + 3, y, z + 2, block)
place_block(x + 4, y, z + 2, block)
place_block(x, y, z + 3, block)
place_block(x + 1, y, z + 3, block)
place_block(x + 2, y, z + 3, block)
place_block(x + 3, y, z + 3, block)
place_block(x + 4, y, z + 3, block)
place_block(x, y, z + 4, block)
place_block(x + 1, y, z + 4, block)
place_block(x + 2, y, z + 4, block)
place_block(x + 3, y, z + 4, block)
place_block(x + 4, y, z + 4, block)
'''
        assert_valid(validate(code, level=1))


# ── 10. Edge cases ──────────────────────────────────────────────────────────

class TestEdgeCases:

    def test_empty_script(self) -> None:
        assert_valid(validate("", level=1))

    def test_only_comments(self) -> None:
        code = "# this is just a comment\n# another comment"
        assert_valid(validate(code, level=1))

    def test_only_import(self) -> None:
        code = "from golem import *"
        assert_valid(validate(code, level=1))

    def test_syntax_error(self) -> None:
        code = "def ("
        assert_invalid(validate(code, level=1), construct="syntax")

    def test_unknown_level(self) -> None:
        code = "from golem import *"
        assert_invalid(validate(code, level=99), construct="level")

    def test_default_level_is_1(self) -> None:
        code = '''\
from golem import *

say("hi")
'''
        assert_valid(validate(code))

    def test_division_not_permitted_level1(self) -> None:
        """Division is excluded at Level 1 to avoid float confusion."""
        code = '''\
from golem import *

x = 10
y = x / 2
'''
        assert_invalid(validate(code, level=1), construct="Div")

    def test_while_loop_not_permitted_level1(self) -> None:
        code = '''\
from golem import *

x = 0
while x < 10:
    x = x + 1
'''
        assert_invalid(validate(code, level=1), construct="While")

    def test_list_literal_not_permitted_level1(self) -> None:
        code = '''\
from golem import *

blocks = ["stone", "cobblestone"]
'''
        assert_invalid(validate(code, level=1), construct="List")

    def test_class_def_not_permitted(self) -> None:
        code = '''\
from golem import *

class Foo:
    pass
'''
        assert_invalid(validate(code, level=1), construct="ClassDef")

    def test_try_except_not_permitted(self) -> None:
        code = '''\
from golem import *

try:
    say("hi")
except:
    pass
'''
        assert_invalid(validate(code, level=1), construct="Try")

    def test_lambda_not_permitted(self) -> None:
        code = '''\
from golem import *

f = lambda x: x + 1
'''
        assert_invalid(validate(code, level=1), construct="Lambda")

    def test_list_comprehension_not_permitted(self) -> None:
        code = '''\
from golem import *

xs = [i for i in range(10)]
'''
        assert_invalid(validate(code, level=1), construct="ListComp")

    def test_augmented_assignment_not_permitted_level1(self) -> None:
        code = '''\
from golem import *

x = 1
x += 1
'''
        assert_invalid(validate(code, level=1), construct="AugAssign")

    def test_f_string_not_permitted(self) -> None:
        code = '''\
from golem import *

name = "Alex"
say(f"hello {name}")
'''
        # f-strings produce JoinedStr/FormattedValue nodes
        assert_invalid(validate(code, level=1))

    def test_string_concatenation_ok(self) -> None:
        """String concat with + is the Level 1 way to build messages."""
        code = '''\
from golem import *

name = "Alex"
say("hello " + name)
'''
        assert_valid(validate(code, level=1))

    def test_multiple_errors_reported(self) -> None:
        """The validator should report all errors, not just the first one."""
        code = '''\
import os

for i in range(10):
    exec("bad")
'''
        result = validate(code, level=1)
        assert not result.valid
        assert len(result.errors) > 1

    def test_keyword_arguments_permitted(self) -> None:
        code = '''\
from golem import *

craft("iron_pickaxe", count=1)
give("cobblestone", count=10)
'''
        assert_valid(validate(code, level=1))

    def test_pass_not_permitted_level1(self) -> None:
        code = '''\
from golem import *

pass
'''
        assert_invalid(validate(code, level=1), construct="Pass")

    def test_while_not_permitted_level2(self) -> None:
        """Level 2 adds For but not While."""
        code = '''\
from golem import *

x = 0
while x < 10:
    x = x + 1
'''
        assert_invalid(validate(code, level=2), construct="While")

    def test_structured_error_has_line_number(self) -> None:
        code = '''\
from golem import *

x = 1
for i in range(10):
    say(str(i))
'''
        result = validate(code, level=1)
        for_errors = [e for e in result.errors if e.construct == "For"]
        assert len(for_errors) > 0
        assert for_errors[0].line == 4
