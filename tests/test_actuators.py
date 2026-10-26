"""Tests for nexgenpy.actuators."""

from typing import Any

import pytest
import requests

from nexgenpy.actuators import (
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT,
    _function_source,
    _request_timeout,
    actuator,
)

VALID_ARGS: dict[str, Any] = {
    "name": "doubler",
    "atype": "coding",
    "version": "1.0.0",
    "is_latest": True,
    "requirements": ["numpy==2.0.0"],
}


def make_actuator(**overrides: Any):
    return actuator(**{**VALID_ARGS, **overrides})


def sample_method(x: int, scale: float = 2.0, label="out"):
    return {label: x * scale}


# --- argument validation ---------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", 123),
        ("name", None),
        ("atype", "encoding"),
        ("atype", None),
        ("version", 1.0),
        ("is_latest", "yes"),
        ("is_latest", 1),
        ("requirements", "numpy"),
        ("requirements", ("numpy",)),
        ("requirements", ["numpy", 3]),
    ],
)
def test_invalid_arguments_raise_value_error(field: str, value: Any):
    with pytest.raises(ValueError, match=field):
        make_actuator(**{field: value})


@pytest.mark.parametrize("atype", ["coding", "decoding"])
def test_both_actuator_types_are_accepted(atype: str):
    assert callable(make_actuator(atype=atype))


@pytest.mark.parametrize("requirements", [None, []])
def test_empty_requirements_are_accepted(requirements: Any):
    assert callable(make_actuator(requirements=requirements))


def test_invalid_argument_is_logged(caplog: pytest.LogCaptureFixture):
    with pytest.raises(ValueError):
        make_actuator(version=1)
    assert "version is invalid" in caplog.text


# --- decorator behaviour ---------------------------------------------------


def test_decorating_does_not_send_a_request(fake_post):
    make_actuator()(sample_method)
    assert fake_post.calls == []


def test_wrapper_keeps_function_metadata():
    wrapped = make_actuator()(sample_method)
    assert wrapped.__name__ == "sample_method"
    assert wrapped.__wrapped__ is sample_method


def test_wrapper_ignores_call_arguments(fake_post):
    wrapped = make_actuator()(sample_method)
    assert wrapped(1, scale=3.0) is True
    assert len(fake_post.calls) == 1


def test_every_call_sends_a_request(fake_post):
    wrapped = make_actuator()(sample_method)
    wrapped()
    wrapped()
    assert len(fake_post.calls) == 2


# --- request payload -------------------------------------------------------


def test_payload_contains_actuator_metadata(fake_post):
    make_actuator()(sample_method)()

    payload = fake_post.last["json"]
    assert payload["name"] == "doubler"
    assert payload["version"] == "1.0.0"
    assert payload["actuator_type"] == "coding"
    assert payload["set_latest"] is True
    assert payload["requirements"] == ["numpy==2.0.0"]


def test_none_requirements_are_sent_as_empty_list(fake_post):
    make_actuator(requirements=None)(sample_method)()
    assert fake_post.last["json"]["requirements"] == []


def test_payload_method_is_source_without_decorator(fake_post):
    @actuator("inner", "decoding", "0.1", False, None)
    def inner(a: int) -> int:
        return a + 1

    inner()

    method = fake_post.last["json"]["method"]
    assert method.startswith("def inner(a: int) -> int:")
    assert "@actuator" not in method
    assert "return a + 1" in method


def test_payload_method_args(fake_post):
    make_actuator()(sample_method)()

    assert fake_post.last["json"]["method_args"] == {
        "x": {"type": str(int)},
        "scale": {"type": str(float), "default": "2.0"},
        "label": {"default": "out"},
    }


def test_payload_method_args_for_function_without_parameters(fake_post):
    def no_args() -> None:
        return None

    make_actuator()(no_args)()
    assert fake_post.last["json"]["method_args"] == {}


# --- request target, headers and timeout -----------------------------------


def test_default_base_url_is_used(fake_post):
    make_actuator()(sample_method)()
    assert fake_post.last["url"] == f"{DEFAULT_BASE_URL}/actuators"


def test_base_url_from_environment(fake_post, monkeypatch):
    monkeypatch.setenv("NEXGEN_BASE_URL", "https://nexgen.example/api/v2")
    make_actuator()(sample_method)()
    assert fake_post.last["url"] == "https://nexgen.example/api/v2/actuators"


def test_base_url_is_read_at_call_time(fake_post, monkeypatch):
    wrapped = make_actuator()(sample_method)
    monkeypatch.setenv("NEXGEN_BASE_URL", "https://late.example")
    wrapped()
    assert fake_post.last["url"] == "https://late.example/actuators"


def test_no_api_key_header_without_env(fake_post):
    make_actuator()(sample_method)()
    assert fake_post.last["headers"] == {}


def test_api_key_header_from_environment(fake_post, monkeypatch):
    monkeypatch.setenv("NEXGEN_API_KEY", "secret")
    make_actuator()(sample_method)()
    assert fake_post.last["headers"] == {"X-API-KEY": "secret"}


def test_request_uses_timeout(fake_post, monkeypatch):
    monkeypatch.setenv("NEXGEN_TIMEOUT", "5")
    make_actuator()(sample_method)()
    assert fake_post.last["timeout"] == 5.0


# --- responses -------------------------------------------------------------


@pytest.mark.parametrize("status_code", [200, 201, 204])
def test_success_status_returns_true(fake_post, status_code: int):
    fake_post.response.status_code = status_code
    fake_post.response.ok = True
    assert make_actuator()(sample_method)() is True


@pytest.mark.parametrize("status_code", [400, 401, 409, 422, 500])
def test_error_status_returns_false(fake_post, caplog, status_code: int):
    fake_post.response.status_code = status_code
    fake_post.response.ok = False
    fake_post.response.text = '{"detail": "nope"}'

    assert make_actuator()(sample_method)() is False
    assert f"status={status_code}" in caplog.text
    assert "nope" in caplog.text


def test_request_exception_returns_false(fake_post, caplog):
    fake_post.error = requests.ConnectionError("connection refused")
    assert make_actuator()(sample_method)() is False
    assert "connection refused" in caplog.text


def test_unexpected_exception_is_not_swallowed(fake_post):
    fake_post.error = RuntimeError("boom")
    with pytest.raises(RuntimeError, match="boom"):
        make_actuator()(sample_method)()


# --- _request_timeout ------------------------------------------------------


def test_timeout_default_when_unset():
    assert _request_timeout() == DEFAULT_TIMEOUT


@pytest.mark.parametrize(("raw", "expected"), [("30", 30.0), ("0.5", 0.5)])
def test_timeout_from_environment(monkeypatch, raw: str, expected: float):
    monkeypatch.setenv("NEXGEN_TIMEOUT", raw)
    assert _request_timeout() == expected


@pytest.mark.parametrize("raw", ["abc", "", "0", "-3"])
def test_invalid_timeout_falls_back_to_default(monkeypatch, caplog, raw: str):
    monkeypatch.setenv("NEXGEN_TIMEOUT", raw)
    assert _request_timeout() == DEFAULT_TIMEOUT
    assert "NEXGEN_TIMEOUT is invalid" in caplog.text


# --- _function_source ------------------------------------------------------


def _passthrough(func):
    return func


def test_function_source_without_decorator():
    source = _function_source(sample_method)
    assert source.startswith("def sample_method(")
    assert source.rstrip().endswith("return {label: x * scale}")


def test_function_source_strips_multiple_decorators():
    @_passthrough
    @_passthrough
    def decorated(a, b):
        return a - b

    source = _function_source(decorated)
    assert source == "def decorated(a, b):\n    return a - b\n"


def test_function_source_strips_multiline_decorator():
    @actuator(
        name="multi",
        atype="coding",
        version="1",
        is_latest=False,
        requirements=None,
    )
    def multi(a):
        return a

    source = _function_source(multi.__wrapped__)
    assert source == "def multi(a):\n    return a\n"


def test_function_source_is_valid_standalone_code():
    @_passthrough
    def adder(a, b=1):
        return a + b

    namespace: dict[str, Any] = {}
    # nosemgrep: python.lang.security.audit.exec-detected.exec-detected
    exec(_function_source(adder), namespace)  # noqa: S102
    assert namespace["adder"](2) == 3
