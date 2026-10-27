"""Synthetic keys: tiny sandboxed Jinja templates that compose new keys from merged ones (see docs/SPEC.md, 0.4).

Template output and input values are secrets. Every error message is built here from a stable code and key names;
Jinja's own message text and any rendered or input value never reach an exception, log line or state.
"""

from __future__ import annotations

import base64
import binascii
import functools
import urllib.parse
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence

from jinja2 import TemplateSyntaxError, nodes
from jinja2 import filters as jinja_filters
from jinja2.runtime import StrictUndefined, missing
from jinja2.sandbox import ImmutableSandboxedEnvironment, SecurityError

MAX_OUTPUT = 65536
JINJA_FILTERS = ("lower", "upper", "trim", "replace", "default", "length", "join", "capitalize", "title")
OWN_FILTERS = ("substr", "urlquote", "b64encode", "b64decode")
RESERVED_NAMES = ("secrets", "self", "loop", "caller", "varargs", "kwargs", "super")  # Jinja internals, bare use
ALLOWED_KEYWORDS = ("boolean", "length")  # default(boolean=...), substr(length=...)
_ALLOWED_NODES = (
    nodes.Template, nodes.Output, nodes.TemplateData, nodes.Const, nodes.If, nodes.Compare, nodes.Operand,
    nodes.And, nodes.Or, nodes.Not, nodes.Neg, nodes.Add, nodes.Concat, nodes.CondExpr, nodes.List, nodes.Tuple,
)
_TEXT = {
    "synthetic_collision": "collides with an existing key",
    "synthetic_forbidden": "template uses a forbidden construct",
    "synthetic_syntax": "template has a syntax error",
    "synthetic_undefined": "references an undefined key",
    "synthetic_too_large": "result is too large",
    "synthetic_error": "template could not be rendered",
}


class SyntheticError(Exception):
    """Stable `code`; the message contains only the code text and key names."""

    def __init__(self, code: str, name: str, detail: str = "") -> None:
        super().__init__(f"synthetic key '{name}': {_TEXT[code]}{detail}")
        self.code = code
        self.name = name


class _TooLarge(Exception):
    pass


class _UndefinedKey(Exception):
    """Raised by the undefined type; carries only the looked-up name."""


class _Undefined(StrictUndefined):
    __slots__ = ()

    def __init__(self, hint: Any = None, obj: Any = missing, name: Any = None, exc: Any = None) -> None:
        super().__init__(hint, obj, name, _UndefinedKey)

    @property
    def _undefined_message(self) -> str:  # type: ignore[override]
        return str(self._undefined_name)


# ---------------------------------------------------------------- filters


def _substr(value: Any, start: Any = 0, length: Any = None) -> str:
    text = str(value)
    begin = int(start)
    begin = max(len(text) + begin, 0) if begin < 0 else begin
    if length is None:
        return text[begin:]
    return text[begin:begin + max(int(length), 0)]


def _urlquote(value: Any) -> str:
    return urllib.parse.quote(str(value), safe="")


def _b64encode(value: Any) -> str:
    return base64.b64encode(str(value).encode("utf-8")).decode("ascii")


def _b64decode(value: Any) -> str:
    try:
        return base64.b64decode(str(value).encode("utf-8"), validate=True).decode("utf-8")
    except (binascii.Error, UnicodeError, ValueError):
        raise ValueError("invalid base64") from None


def _capped(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Stop filters (e.g. chained replace) from blowing up memory before the final output check."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        result = fn(*args, **kwargs)
        if isinstance(result, str) and len(result) > MAX_OUTPUT:
            raise _TooLarge
        return result

    return wrapper


def _filters() -> dict[str, Callable[..., Any]]:
    out = {name: _capped(jinja_filters.FILTERS[name]) for name in JINJA_FILTERS}
    out.update(substr=_capped(_substr), urlquote=_capped(_urlquote), b64encode=_capped(_b64encode),
               b64decode=_capped(_b64decode))
    return out


def _environment() -> ImmutableSandboxedEnvironment:
    env = ImmutableSandboxedEnvironment(undefined=_Undefined, autoescape=False, loader=None, extensions=[],
                                        keep_trailing_newline=True)
    env.globals.clear()
    env.filters = _filters()
    env.tests = {}
    return env


# ---------------------------------------------------------------- AST whitelist


class _Forbidden(Exception):
    pass


def _check(node: nodes.Node, allowed: set[str]) -> None:
    if isinstance(node, nodes.Name):
        if node.ctx != "load" or node.name.startswith("__") or node.name in RESERVED_NAMES:
            raise _Forbidden
        return
    if isinstance(node, nodes.Getitem):
        base = node.node
        if not (isinstance(base, nodes.Name) and base.name == "secrets" and base.ctx == "load"):
            raise _Forbidden
        _check(node.arg, allowed)
        return
    if isinstance(node, nodes.Filter):
        if (node.name not in allowed or node.node is None or node.dyn_args is not None
                or node.dyn_kwargs is not None):
            raise _Forbidden
        _check(node.node, allowed)
        for arg in node.args:
            _check(arg, allowed)
        for kw in node.kwargs:
            if not isinstance(kw, nodes.Keyword) or kw.key not in ALLOWED_KEYWORDS:
                raise _Forbidden
            _check(kw.value, allowed)
        return
    if not isinstance(node, _ALLOWED_NODES):
        raise _Forbidden
    for child in node.iter_child_nodes():
        _check(child, allowed)


def _referenced_names(tree: nodes.Node) -> set[str]:
    """Names the template mentions literally (the only ones that may appear in an undefined error)."""
    found = {n.name for n in tree.find_all(nodes.Name)}
    found.update(c.value for c in tree.find_all(nodes.Const) if isinstance(c.value, str))
    return found


# ---------------------------------------------------------------- public API


def apply(secrets: Mapping[str, str], defs: Sequence[tuple[str, str]]) -> dict[str, str]:
    """Render every (name, template). Returns only the synthetic keys; the caller merges them.

    Synthetic keys see only the real `secrets`, never each other. Raises SyntheticError.
    """
    if not defs:
        return {}
    taken = set(secrets)
    for name, _ in defs:
        if name in taken:
            raise SyntheticError("synthetic_collision", name, " (real key of the same name)")
        taken.add(name)
    env = _environment()
    allowed = set(env.filters)
    real = MappingProxyType(dict(secrets))
    context: dict[str, Any] = {k: v for k, v in secrets.items() if k.isidentifier() and not k.startswith("__")}
    context["secrets"] = real
    out: dict[str, str] = {}
    for name, template in defs:
        try:
            tree = env.parse(template)
        except TemplateSyntaxError:
            raise SyntheticError("synthetic_syntax", name) from None
        except Exception:
            raise SyntheticError("synthetic_error", name) from None
        try:
            _check(tree, allowed)
        except _Forbidden:
            raise SyntheticError("synthetic_forbidden", name) from None
        try:
            value = str(env.from_string(template).render(context))
        except _UndefinedKey as exc:
            ref = str(exc)
            detail = f" (key '{ref}')" if ref in _referenced_names(tree) else ""
            raise SyntheticError("synthetic_undefined", name, detail) from None
        except _TooLarge:
            raise SyntheticError("synthetic_too_large", name) from None
        except SecurityError:
            raise SyntheticError("synthetic_forbidden", name) from None
        except Exception:
            raise SyntheticError("synthetic_error", name) from None
        if len(value) > MAX_OUTPUT:
            raise SyntheticError("synthetic_too_large", name)
        out[name] = value
    return out
