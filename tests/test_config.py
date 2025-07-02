import pytest

from typecheck import TypeCheckError, config, typecheck


def test_config_defaults_injected():
    # Ensure initial defaults
    config.strict_mode = True
    config.sample_size = 2

    @typecheck()  # no explicit args: inherits strict_mode
    def f(x: int):
        return x

    f(1)
    try:
        f("a")  # type: ignore
    except TypeCheckError:
        pass
    else:
        assert False, "Expected TypeCheckError under global strict_mode"
    # restore defaults for other tests
    from typecheck import config as _cfg

    _cfg.reset()


def test_config_sample_size_applied():
    config.reset()
    config.sample_size = 2

    @typecheck()
    def g(items: list[int]):
        return len(items)

    # 3rd element wrong but outside sample window
    g([1, 2, "bad"])  # type: ignore

    # deep override via decorator arg should still work
    @typecheck(deep=True)
    def h(items: list[int]):
        return len(items)

    try:
        h([1, 2, "bad"])  # type: ignore
    except TypeCheckError:
        pass
    else:
        assert False, "Expected TypeCheckError with deep=True overriding global sample_size"
    # restore defaults for other tests
    from typecheck import config as _cfg

    _cfg.reset()


def test_config_set_sample_size_invalid_and_custom_validators_fallback(monkeypatch=None):
    # Negative / zero should raise
    from typecheck import config as _cfg

    _cfg.reset()
    for bad in [0, -1]:
        raised = False
        try:
            _cfg.set_sample_size(bad)  # type: ignore[arg-type]
        except ValueError:
            raised = True
        assert raised, "Expected ValueError for non-positive sample size"

    # Simulate failure by temporarily patching __import__ to raise for validators
    import builtins

    real_import = builtins.__import__

    def failing_import(name, globals=None, locals=None, fromlist=(), level=0):
        if (fromlist and "validators" in fromlist) or name.endswith(".validators"):
            raise ImportError("simulated")
        return real_import(name, globals, locals, fromlist, level)

    builtins.__import__ = failing_import  # type: ignore
    try:
        empty = _cfg.custom_validators
        assert empty == {}, f"Expected empty dict fallback when validators import fails, got {empty}"
    finally:
        builtins.__import__ = real_import  # type: ignore


def test_config_invalid_sample_size():
    # Explicit simple invalid sample size (0) distinct from looped test above
    from typecheck import config as _cfg

    with pytest.raises(ValueError):  # type: ignore[name-defined]
        _cfg.set_sample_size(0)


def test_config_policy_invalid():
    from typecheck import config as _cfg

    with pytest.raises(ValueError):  # type: ignore[name-defined]
        _cfg.set_fallback_policy("nope")
    with pytest.raises(ValueError):  # type: ignore[name-defined]
        _cfg.set_forward_ref_policy("nope")


def test_config_reset_and_sample_sync():
    from typecheck import config as _cfg
    from typecheck import utils as _utils  # type: ignore

    _cfg.set_sample_size(7)
    assert _cfg.sample_size == 7
    assert _utils.DEFAULT_SAMPLE_SIZE == 7
    _cfg.reset()
    assert _cfg.sample_size == 5  # default
    assert _utils.DEFAULT_SAMPLE_SIZE == 5


def test_fallback_policy_error_for_unsupported():
    # Transition fallback policy to error and ensure unsupported annotation triggers TypeCheckError
    from typecheck import TypeCheckError
    from typecheck import config as _cfg  # type: ignore
    from typecheck import typecheck

    _cfg.set_fallback_policy("error")
    unsupported = 123

    @typecheck()
    def j(x: unsupported):  # type: ignore  # value used as annotation
        return x

    with pytest.raises(TypeCheckError):  # type: ignore[name-defined]
        j("abc")
    _cfg.set_fallback_policy("silent")


def test_warn_fallback_policy(capsys):
    import warnings

    from typecheck import config as _cfg
    from typecheck import typecheck

    _cfg.set_fallback_policy("warn")
    dummy = 123
    with warnings.catch_warnings(record=True) as w:  # pragma: no branch - assertion encloses
        warnings.simplefilter("always")

        @typecheck()
        def g(x: dummy):  # type: ignore
            return x

        g(5)
        assert any("unsupported type construct" in str(m.message) for m in w)
    _cfg.set_fallback_policy("silent")


def test_forward_ref_strict_policy():
    from typecheck import TypeCheckError
    from typecheck import config as _cfg  # type: ignore
    from typecheck import typecheck

    _cfg.set_forward_ref_policy("strict")

    @typecheck()
    def h(x: "UnknownType"):  # type: ignore[name-defined]
        return x

    with pytest.raises(TypeCheckError):  # type: ignore[name-defined]
        h(5)
    _cfg.set_forward_ref_policy("permissive")
