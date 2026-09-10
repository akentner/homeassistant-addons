#!/usr/bin/env python3
"""Prove the truth table of the `opencode` job gate in .github/workflows/opencode.yml.

The workflow is comment-triggered on a PUBLIC repository, so its job-level `if:` is the only thing
standing between a drive-by commenter and a job whose environment holds MINIMAX_API_KEY. This script
does not check that the workflow parses; it extracts the `if:` expression out of the file, evaluates
it against every documented `author_association` value crossed with every trigger-shaped comment
body, and asserts two invariants:

  parity  the gate is truth-table-identical to the pre-change body-only expression for the three
          trusted associations (OWNER, MEMBER, COLLABORATOR) -- the author clause added a
          restriction and changed no body semantics.
  denial  the gate is false for the five untrusted associations across every body fixture.

Three controls keep a green run from being vacuous: the embedded pre-change expression must still
evaluate TRUE for NONE + '/oc' (otherwise the harness can no longer see the hole it guards), the
post-change expression must still be TRUE for OWNER + '/oc' (otherwise the gate shut everything
off), and an expression using an unmodelled function must raise (otherwise an unparsed gate could
silently evaluate as anything at all).

Exit codes: 0 all assertions hold; 1 an assertion failed; 2 the workflow or its `if:` is unreadable;
3 the verifier itself is broken (a control failed).
"""

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

DEFAULT_WORKFLOW = Path(".github/workflows/opencode.yml")

# Retained as the DETECTABILITY CONTROL, not as the thing under test. Copied verbatim from
# .github/workflows/opencode.yml at commit 1a8406f (pre-change HEAD): the four body-only
# alternatives with no author clause. Assertion A3 requires this to still evaluate TRUE for
# author_association == 'NONE' with body '/oc'. If it ever reports FALSE, this harness can no
# longer observe the exposure it exists to guard, and the verifier must fail as broken rather
# than print a pass.
PRE_CHANGE_EXPRESSION = """
contains(github.event.comment.body, ' /oc') ||
startsWith(github.event.comment.body, '/oc') ||
contains(github.event.comment.body, ' /opencode') ||
startsWith(github.event.comment.body, '/opencode')
"""

# The GitHub-documented author_association values. Trust set per decision D-01.
TRUSTED_ASSOCIATIONS = ("OWNER", "MEMBER", "COLLABORATOR")
UNTRUSTED_ASSOCIATIONS = ("CONTRIBUTOR", "FIRST_TIME_CONTRIBUTOR", "FIRST_TIMER", "MANNEQUIN", "NONE")
ALL_ASSOCIATIONS = tuple(sorted(TRUSTED_ASSOCIATIONS + UNTRUSTED_ASSOCIATIONS))

# Comment bodies. The last three are non-triggering; '/OC' and '/october is a month' encode the
# PRE-EXISTING looseness of the body clause (case-insensitive comparison, and startsWith('/oc')
# matching '/october'). That looseness is recorded truthfully here, not silently fixed.
BODY_FIXTURES = (
    "/oc",
    "/opencode",
    "please /oc run the tests",
    "see /opencode",
    "/OC",
    "/october is a month",
    "refactor this",
    "",
    "nothing/oc",
)

# An expression the evaluator must NOT be able to evaluate (assertion A5).
UNSUPPORTED_EXPRESSION = "fromJSON(github.event.comment.body)[0] == 'x'"


class UnsupportedConstruct(Exception):
    """Raised when the evaluator meets a token, function or context path it does not model.

    Never caught to produce a boolean. A silent `false` here would report a gate as closed when
    it was merely unparsed; a silent `true` would be worse.
    """


class Tokenizer:
    """Split a GitHub Actions expression into the tokens this evaluator models."""

    OPERATORS = ("==", "!=", "&&", "||", "!", "(", ")", ",")

    def __init__(self, source: str) -> None:
        self.source = source
        self.pos = 0
        self.tokens: list[tuple[str, Any]] = []

    def tokenize(self) -> list[tuple[str, Any]]:
        """Return a list of (kind, value) tokens; raise UnsupportedConstruct on anything else."""
        while self.pos < len(self.source):
            char = self.source[self.pos]
            if char in " \t\r\n":
                self.pos += 1
                continue
            if char == "'":
                self.tokens.append(("string", self._read_string()))
                continue
            operator = self._read_operator()
            if operator is not None:
                self.tokens.append(("op", operator))
                continue
            if char.isdigit():
                self.tokens.append(("number", self._read_number()))
                continue
            if char.isalpha() or char == "_":
                self.tokens.append(self._read_word())
                continue
            raise UnsupportedConstruct(f"unmodelled character {char!r} at offset {self.pos}")
        self.tokens.append(("end", None))
        return self.tokens

    def _read_operator(self) -> str | None:
        for operator in self.OPERATORS:
            if self.source.startswith(operator, self.pos):
                self.pos += len(operator)
                return operator
        return None

    def _read_string(self) -> str:
        self.pos += 1  # opening quote
        chars: list[str] = []
        while self.pos < len(self.source):
            char = self.source[self.pos]
            if char == "'":
                if self.source.startswith("''", self.pos):  # '' escapes a single quote
                    chars.append("'")
                    self.pos += 2
                    continue
                self.pos += 1
                return "".join(chars)
            chars.append(char)
            self.pos += 1
        raise UnsupportedConstruct("unterminated single-quoted string literal")

    def _read_number(self) -> float:
        start = self.pos
        while self.pos < len(self.source) and (self.source[self.pos].isdigit() or self.source[self.pos] == "."):
            self.pos += 1
        return float(self.source[start : self.pos])

    def _read_word(self) -> tuple[str, Any]:
        start = self.pos
        while self.pos < len(self.source) and (self.source[self.pos].isalnum() or self.source[self.pos] in "_."):
            self.pos += 1
        word = self.source[start : self.pos]
        if word == "true":
            return ("bool", True)
        if word == "false":
            return ("bool", False)
        if word == "null":
            return ("null", None)
        return ("word", word)


class Evaluator:
    """Evaluate the subset of the GitHub Actions expression grammar this workflow actually uses.

    Modelled: single-quoted strings ('' escapes a quote), true/false/null, numbers, dotted context
    paths, contains(search, item), startsWith(str, prefix), == != ! && || and parentheses.
    Precedence: ! > ==/!= > && > ||. String comparison, contains and startsWith are all
    case-INSENSITIVE, matching GitHub. `&&` yields its first falsy operand else the last; `||`
    yields its first truthy operand else the last. Falsy: false, 0, '', null.

    Everything else -- any other function, any context path absent from the supplied context --
    raises UnsupportedConstruct.
    """

    FUNCTIONS = ("contains", "startswith")

    def __init__(self, context: dict[str, Any]) -> None:
        self.context = context
        self.tokens: list[tuple[str, Any]] = []
        self.index = 0

    def evaluate(self, expression: str) -> Any:
        """Evaluate an expression and return its GitHub-Actions value (not coerced to bool)."""
        self.tokens = Tokenizer(expression).tokenize()
        self.index = 0
        value = self._parse_or()
        kind, token = self._peek()
        if kind != "end":
            raise UnsupportedConstruct(f"trailing token {token!r} after a complete expression")
        return value

    def evaluate_bool(self, expression: str) -> bool:
        """Evaluate an expression and return its truthiness, as a job-level `if:` is interpreted."""
        return self.truthy(self.evaluate(expression))

    @staticmethod
    def truthy(value: Any) -> bool:
        """GitHub's falsy set is false, 0, the empty string and null; everything else is truthy."""
        if value is None or value is False:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return value != ""
        raise UnsupportedConstruct(f"cannot take the truthiness of {type(value).__name__}")

    def _peek(self) -> tuple[str, Any]:
        return self.tokens[self.index]

    def _next(self) -> tuple[str, Any]:
        token = self.tokens[self.index]
        self.index += 1
        return token

    def _accept_op(self, *operators: str) -> str | None:
        kind, value = self._peek()
        if kind == "op" and value in operators:
            self.index += 1
            return value
        return None

    def _expect_op(self, operator: str) -> None:
        if self._accept_op(operator) is None:
            kind, value = self._peek()
            raise UnsupportedConstruct(f"expected {operator!r} but found {value!r} (kind {kind})")

    def _parse_or(self) -> Any:
        value = self._parse_and()
        while self._accept_op("||") is not None:
            right = self._parse_and()
            value = value if self.truthy(value) else right
        return value

    def _parse_and(self) -> Any:
        value = self._parse_equality()
        while self._accept_op("&&") is not None:
            right = self._parse_equality()
            value = right if self.truthy(value) else value
        return value

    def _parse_equality(self) -> Any:
        value = self._parse_unary()
        while True:
            operator = self._accept_op("==", "!=")
            if operator is None:
                return value
            right = self._parse_unary()
            equal = self._equals(value, right)
            value = equal if operator == "==" else not equal

    def _parse_unary(self) -> Any:
        if self._accept_op("!") is not None:
            return not self.truthy(self._parse_unary())
        return self._parse_primary()

    def _parse_primary(self) -> Any:
        if self._accept_op("(") is not None:
            value = self._parse_or()
            self._expect_op(")")
            return value
        kind, token = self._next()
        if kind in ("string", "bool", "number", "null"):
            return token
        if kind == "word":
            if self._peek() == ("op", "("):
                return self._call_function(token)
            return self._resolve_path(token)
        raise UnsupportedConstruct(f"unmodelled token {token!r} (kind {kind})")

    def _call_function(self, name: str) -> Any:
        if name.lower() not in self.FUNCTIONS:
            raise UnsupportedConstruct(f"unmodelled function {name!r}")
        self._expect_op("(")
        arguments = [self._parse_or()]
        while self._accept_op(",") is not None:
            arguments.append(self._parse_or())
        self._expect_op(")")
        if len(arguments) != 2:
            raise UnsupportedConstruct(f"{name}() modelled with 2 arguments, got {len(arguments)}")
        left, right = arguments
        if not isinstance(left, str) or not isinstance(right, str):
            raise UnsupportedConstruct(f"{name}() modelled for string arguments only")
        if name.lower() == "contains":
            return right.casefold() in left.casefold()
        return left.casefold().startswith(right.casefold())

    def _resolve_path(self, path: str) -> Any:
        current: Any = self.context
        for segment in path.split("."):
            if not isinstance(current, dict) or segment not in current:
                raise UnsupportedConstruct(f"unmodelled context path {path!r} (at segment {segment!r})")
            current = current[segment]
        return current

    @staticmethod
    def _equals(left: Any, right: Any) -> bool:
        """GitHub compares strings case-insensitively; other modelled types compare by value."""
        if isinstance(left, str) and isinstance(right, str):
            return left.casefold() == right.casefold()
        if isinstance(left, str) != isinstance(right, str):
            raise UnsupportedConstruct("unmodelled mixed-type comparison")
        return bool(left == right)


def load_gate_expression(workflow: Path, job: str) -> str:
    """Read jobs.<job>.if out of the workflow file. Exit 2 if the file or the key path is absent."""
    if not workflow.is_file():
        print(f"FAIL: workflow not found: {workflow}", flush=True)
        raise SystemExit(2)
    try:
        document = yaml.safe_load(workflow.read_text())
    except yaml.YAMLError as error:
        print(f"FAIL: {workflow}: YAML parse error: {error}", flush=True)
        raise SystemExit(2) from error
    try:
        expression = document["jobs"][job]["if"]
    except (KeyError, TypeError) as error:
        print(f"FAIL: {workflow}: no jobs.{job}.if key path ({error})", flush=True)
        raise SystemExit(2) from error
    if not isinstance(expression, str) or not expression.strip():
        print(f"FAIL: {workflow}: jobs.{job}.if is not a non-empty string", flush=True)
        raise SystemExit(2)
    return expression


def make_context(association: str, body: str) -> dict[str, Any]:
    """Build a full synthetic github.event.comment context so no path resolves by accident."""
    return {
        "github": {
            "event_name": "issue_comment",
            "event": {
                "action": "created",
                "comment": {
                    "id": 1,
                    "body": body,
                    "author_association": association,
                    "user": {"login": "fixture", "type": "User"},
                    "html_url": "https://example.invalid/comment/1",
                },
            },
        },
    }


def evaluate_matrix(expression: str) -> dict[tuple[str, str], bool]:
    """Evaluate one expression over every (association, body) fixture pair."""
    return {
        (association, body): Evaluator(make_context(association, body)).evaluate_bool(expression)
        for association in ALL_ASSOCIATIONS
        for body in BODY_FIXTURES
    }


def print_table(gate: dict[tuple[str, str], bool], control: dict[tuple[str, str], bool]) -> None:
    """Print all 72 rows: association x body, with the file expression next to the control."""
    print(f"{'author_association':<24} {'comment body':<28} {'file if:':<9} {'pre-change':<10} verdict", flush=True)
    print("-" * 84, flush=True)
    for association in ALL_ASSOCIATIONS:
        trusted = association in TRUSTED_ASSOCIATIONS
        for body in BODY_FIXTURES:
            new = gate[(association, body)]
            old = control[(association, body)]
            if trusted:
                verdict = "parity" if new == old else "PARITY BREACH"
            else:
                verdict = "denied" if not new else "ALLOWED — HOLE"
            label = repr(body) if body else "'' (empty)"
            print(f"{association:<24} {label:<28} {str(new):<9} {str(old):<10} {verdict}", flush=True)


def check_grammar_guard() -> tuple[bool, str]:
    """A5: an unmodelled construct must raise, never degrade to a boolean."""
    context = make_context("OWNER", "/oc")
    try:
        result = Evaluator(context).evaluate_bool(UNSUPPORTED_EXPRESSION)
    except UnsupportedConstruct as error:
        return True, f"raised UnsupportedConstruct: {error}"
    return False, f"silently returned {result!r} for {UNSUPPORTED_EXPRESSION!r}"


def main() -> int:
    """Extract the gate expression, prove parity and denial, and report every control."""
    parser = argparse.ArgumentParser(
        description="Prove the opencode job gate's truth table by evaluating the expression in the workflow file.",
        epilog=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--workflow", type=Path, default=DEFAULT_WORKFLOW, help="workflow file to read the gate from")
    parser.add_argument("--job", default="opencode", help="job id whose `if:` is under test")
    parser.add_argument("--quiet", action="store_true", help="print only the assertion summary")
    args = parser.parse_args()

    expression = load_gate_expression(args.workflow, args.job)

    # A5 first: if the grammar guard is broken, nothing below can be trusted.
    guard_ok, guard_detail = check_grammar_guard()

    try:
        gate = evaluate_matrix(expression)
        control = evaluate_matrix(PRE_CHANGE_EXPRESSION)
    except UnsupportedConstruct as error:
        print(f"FAIL: gate expression uses a construct this verifier does not model: {error}", flush=True)
        print("      Extend the evaluator; do NOT let an unparsed gate report as closed.", flush=True)
        return 2

    if not args.quiet:
        print(f"workflow: {args.workflow}   job: {args.job}", flush=True)
        print(f"gate expression under test:\n{expression.strip()}\n", flush=True)
        print_table(gate, control)
        print("", flush=True)

    parity_failures = [
        (association, body)
        for association in TRUSTED_ASSOCIATIONS
        for body in BODY_FIXTURES
        if gate[(association, body)] != control[(association, body)]
    ]
    denial_failures = [
        (association, body)
        for association in UNTRUSTED_ASSOCIATIONS
        for body in BODY_FIXTURES
        if gate[(association, body)]
    ]
    detectability_ok = control[("NONE", "/oc")]
    positive_ok = gate[("OWNER", "/oc")]

    results = [
        ("A1 parity", not parity_failures, f"{len(parity_failures)} mismatched trusted rows: {parity_failures[:5]}"),
        ("A2 denial", not denial_failures, f"{len(denial_failures)} untrusted rows allowed: {denial_failures[:5]}"),
        ("A3 detectability control", detectability_ok, "pre-change expression is FALSE for NONE + '/oc'"),
        ("A4 positive control", positive_ok, "file expression is FALSE for OWNER + '/oc' — gate shut everything off"),
        ("A5 grammar guard", guard_ok, guard_detail),
    ]

    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f" — {detail}"), flush=True)

    broken = [name for name, ok, _ in results if not ok and name.startswith(("A3", "A5"))]
    failed = [name for name, ok, _ in results if not ok]

    if broken:
        print(f"\nVERIFIER BROKEN: {', '.join(broken)} — a control failed, so no pass can be reported.", flush=True)
        return 3
    if failed:
        print(f"\nFAIL: {', '.join(failed)}", flush=True)
        return 1
    print(f"\nPASS: all 5 assertions hold over {len(gate)} fixture rows.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
