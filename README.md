<div align="center">

# runtypecheck

Fast, pragmatic runtime type checking for Python 3.10+: a configurable `@typecheck` decorator (and class wrapper) featuring structural `Protocol` validation, constrained & bound `TypeVar` handling, iterable sampling, lazy iterator inspection, async support, custom validators, and a weak-reference LRU cache.

</div>

---

## Why?

Static type checkers (mypy, pyright, pyre) are invaluable before runtime. This library adds inexpensive runtime assurance at the *boundaries* where static analysis may be weak: plugin entry points, notebook experiments, dynamically constructed data, tests, or external inputs. Design goals:

* Pragmatic: unknown / future typing forms are accepted by default (configurable fallback policy).
* Fast: caches resolved hints & origins, samples containers, and short‑circuits early.
* Focused: only one decorator + a small config surface; no metaclass trickery.
* Extensible: drop-in custom validators with a tiny decorator.

---
## Quick Start

```python
from typecheck import typecheck, TypeCheckError

@typecheck()
def greet(name: str, times: int = 1) -> str:
    return ' '.join([f'Hello {name}!'] * times)

print(greet('Alice', 2))          # OK
try:
    greet('Bob', 'x')              # type: ignore
except TypeCheckError as e:
    print('Caught:', e)
```

Apply to a class to wrap all public methods (plus `__init__` / `__call__`).

```python
@typecheck()
class Calc:
    def add(self, a: int, b: int) -> int: return a + b

Calc().add(1, 2)
```

---
## Feature Matrix

| Category | Support Summary |
|----------|-----------------|
| Primitives / builtins | Standard `isinstance` semantics |
| Container generics | `list`, `tuple` (fixed & variadic), `set`, `frozenset`, `dict`, `deque` + ABCs (`Sequence`, `Mapping`, `Iterable`, `Iterator`) |
| Collections sampling | Validates up to N elements (configurable) unless deep mode |
| Unions & Optional | Full branch validation with aggregated mismatch context |
| `Literal[...]` | Membership check |
| `Callable` | Light structural check: positional arity & simple annotation compatibility |
| `Type[Cls]` | Class identity / subclass acceptance |
| `Final` / `ClassVar` | Inner type validated |
| Structural `Protocol` | Attributes & method signature compatibility (positional params & annotations + return) |
| `TypeVar` | Constraint / bound enforcement + per-call consistent binding |
| `Annotated[T, ...]` | Treated as `T` (metadata ignored) |
| `TypedDict` | Required keys + per-key value validation; extra keys allowed (PEP 589 semantics) |
| `NewType` | Validated against its underlying supertype |
| `Never` | Always error if a runtime value is supplied |
| `NoReturn` | Accepted for parameter context (enforced on returns elsewhere) |
| `LiteralString` (3.11+) | Treated as `str` (best effort) |
| `TypeGuard[T]` | Ensures runtime bool result |
| Forward refs | Permissive or strict (config) |
| Async functions | Wrapper preserves `async` and validates awaited result |
| Lazy iterables | Non-length iterables sampled via `itertools.tee` |
| Deep vs sample | `deep=True` overrides sampling; otherwise first *N* elements |
| Custom validators | `@register_validator(cls)` mapping exact type -> predicate |
| Runtime disable | `TYPECHECK_DISABLED=1` env var skips decoration logic |

Unsupported / unrecognized constructs (e.g., advanced future typing forms) fall back to acceptance unless `config.fallback_policy` is set to `warn` or `error`.

---
## Installation

```bash
pip install runtypecheck
```

Python 3.10–3.13 (tested). Zero runtime dependencies.

---
## Usage Examples

### Collections & Sampling
```python
from typecheck import typecheck, TypeCheckError

@typecheck(sample=3)   # only first 3 elements of large list validated
def head_sum(values: list[int]) -> int:
    return sum(values[:3])

@typecheck(deep=True)  # validate every element
def full_sum(values: list[int]) -> int:
    return sum(values)

head_sum([1,2,3,'x',5])         # OK (sampling hides later mismatch)  # type: ignore
try:
    full_sum([1,2,3,'x',5])     # type: ignore
except TypeCheckError: pass
```

### Protocols & TypeVars
```python
from typing import Protocol, TypeVar
from typecheck import typecheck, TypeCheckError

class SupportsClose(Protocol):
    def close(self) -> None: ...

@typecheck()
def shutdown(r: SupportsClose) -> None: r.close()

T = TypeVar('T', int, str)
@typecheck()
def echo(x: T) -> T: return x
```

### Custom Validator
```python
from typecheck import register_validator, typecheck, TypeCheckError

class PositiveInt(int):
    pass

@register_validator(PositiveInt)
def _validate_positive(v, t): return isinstance(v, int) and v >= 0

@typecheck()
def square(x: PositiveInt) -> int: return x * x
```

### Async
```python
import asyncio
from typecheck import typecheck

@typecheck()
async def fetch(n: int) -> int:
    return n * 2

asyncio.run(fetch(5))
```

### Strict Modes & Method Selection
Wrap only selected methods or ignore specific ones:

```python
from typecheck import typecheck

@typecheck(include=["process", "finalize"], exclude=["finalize"])  # only "process" gets wrapped
class Job:
    def process(self, x: int) -> int: return x
    def finalize(self, x: int) -> int: return x  # excluded
    def helper(self, x: int) -> int: return x  # not in include list

class Service:
    @typecheck(ignore=True)  # marker to skip when class decorated
    def fast_path(self, x: int) -> int: return x
    @typecheck()
    def strict_path(self, x: int) -> int: return x

Service = typecheck()(Service)
```

Parameters:
* `include=[...]`: Only listed methods (plus `__init__` / `__call__`).
* `exclude=[...]`: Remove methods after inclusion filtering.
* Per-method `@typecheck(ignore=True)`: Skip even under class decorator.

```python
from typecheck import typecheck, config

config.strict_mode = True          # missing parameter annotations raise
config.strict_return_mode = True   # missing return annotations raise
```

---
## Configuration (`typecheck.config`)

| Attribute | Default | Effect |
|-----------|---------|--------|
| `sample_size` | 5 | Default element sample for collections / iterables |
| `strict_mode` | False | Enforce all parameters annotated |
| `strict_return_mode` | False | Enforce return annotation presence (independent of `strict_mode`) |
| `deep_checking` | False | If True, decorator defaults to deep validation when `deep` not passed |
| `lazy_iterable_validation` | True | Sample first N elements of single‑pass iterables via `itertools.tee` |
| `fallback_policy` | "silent" | Behavior for unsupported constructs: silent / warn / error |
| `forward_ref_policy` | "permissive" | Unresolved forward refs: permissive accept or strict error |

Per‑call overrides: `@typecheck(sample=10)`, `@typecheck(deep=True)`, `@typecheck(strict=True)`, etc.

Reset to defaults:
```python
from typecheck import config
config.reset()
```

---
## Fallback Policy

If a construct is unrecognized, `_check_type` accepts it by default (policy `silent`). Change behavior:

```python
from typecheck import config
config.set_fallback_policy("warn")   # or "error"
```

`warn` emits a `RuntimeWarning`; `error` raises immediately.

---
## Error Messages

Errors raise `TypeCheckError` with a concise diagnostic:

```
Type mismatch for parameter 'age' in function 'greet': expected int, got str ('twenty-five')
```

Return mismatches use: `Return value type mismatch in function 'func': expected list[int], got dict (...)`.

---
## Performance Notes

* Cached: resolved `get_type_hints` + origin/args via weak LRU caches.
* Sampling: limits deep traversal cost for large structures & streams.
* Iterables: lazy path avoids exhausting one‑shot generators.
* Overhead on simple primitive calls is typically a handful of microseconds (implementation detail; measure in your environment).

Disable entirely with an environment variable:

```bash
TYPECHECK_DISABLED=1 python your_app.py
```

---
## Custom Validators API

```python
from typecheck import register_validator

@register_validator(MyType)
def validate(value, expected_type) -> bool:
    # return True / False or raise TypeCheckError for custom message
    ...
```

Validators run before built‑in generic origin handlers.

---
## Weak LRU Cache Utility

`typecheck.weak_lru.lru_cache(maxsize=..., typed=False)` behaves like `functools.lru_cache` but stores per‑instance caches for methods in a `WeakKeyDictionary` so instances can be GC’d.

```python
from typecheck import weak_lru

@weak_lru.lru_cache(maxsize=256)
def fib(n: int) -> int:
    return n if n < 2 else fib(n-1)+fib(n-2)
```

Use `.cache_info()` / `.cache_clear()` same as stdlib.

---
## Advanced Topics

* Deep vs Sampled: `@typecheck(deep=True)` enforces full traversal; otherwise first `sample_size` (config or decorator arg) elements validated.
* Lazy Iterables: When `lazy_iterable_validation` is True and object lacks `__len__`, the library samples via `itertools.tee` without consuming the original iterator.
* Protocol Enumeration: Methods, properties, classmethods, staticmethods, and annotated attributes all counted as required members.
* TypeVar Binding: A fresh context per function call enforces consistent multi-parameter binding (subtype-compatible reuse accepted).
* TypeGuard: Treated as `bool` sanity gate.

---
## Testing

The project ships with a comprehensive pytest suite (async, protocols, lazy iterables, custom validators, strict returns, weak LRU). Run:

```bash
pytest --cov=src/typecheck --cov-report=term-missing
```

---
## Roadmap (Abridged)

* Finer-grained Callable variance & keyword kind checking
* Optional stricter Protocol variance rules
* Configurable error formatter hook
* Extended TypedDict total / optional key strictness flags
* Richer metadata usage for `Annotated`

---
## Packaging & Type Information

The distribution includes a `py.typed` marker so static type checkers (mypy, pyright) can consume inline type hints.

Supported Python versions: 3.10, 3.11, 3.12, 3.13.

Partially handled (best-effort) constructs: `LiteralString` (treated as `str`), `Annotated` (metadata ignored). Unsupported advanced forms like `ParamSpec`, `Concatenate`, `Unpack`, `Required` / `NotRequired`, `Self` currently fall back per the fallback policy.

---
## License

AGPL-3.0-or-later. See `LICENSE`.

Rationale: AGPL ensures improvements to the runtime validation mechanics remain available to the community even when
used over a network (a common deployment style for frameworks and services). This license choice is intentional and
will not be changed or re-licensed under a more permissive variant.

---
## Cheat Sheet

| Want | Use |
|------|-----|
| Enforce parameter annotations globally | `config.strict_mode = True` |
| Enforce return annotations too | `config.strict_return_mode = True` |
| Disable sampling for a call | `@typecheck(deep=True)` |
| Increase sampling globally | `config.set_sample_size(10)` |
| Custom validator | `@register_validator(MyType)` |
| Skip runtime cost (env) | `TYPECHECK_DISABLED=1` |
| Validate generator lazily | leave `config.lazy_iterable_validation = True` |
| Strict on one function only | `@typecheck(strict=True)` |

---
Happy checking!
