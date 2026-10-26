"""Shared fixtures for the nexgenpy tests."""

from typing import Any, Dict, List

import pytest
import requests

from nexgenpy import actuators


class FakeResponse:
    """A minimal stand-in for requests.Response."""

    def __init__(
        self,
        status_code: int = 201,
        text: str = "{}",
        payload: Any = None,
    ) -> None:
        self.status_code = status_code
        self.text = text
        self.ok = status_code < 400
        self.payload = payload

    def json(self) -> Any:
        return self.payload

    def raise_for_status(self) -> None:
        if self.ok is False:
            raise requests.HTTPError(f"{self.status_code} Error", response=self)


class FakePost:
    """Records the calls to a requests verb and returns a preset response."""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []
        self.response = FakeResponse()
        self.error: Exception | None = None

    def __call__(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        if self.error is not None:
            raise self.error
        return self.response

    @property
    def last(self) -> Dict[str, Any]:
        assert self.calls, "requests.post was not called"
        return self.calls[-1]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make sure the Nexgen environment variables of the host do not leak in."""
    for var in ("NEXGEN_BASE_URL", "NEXGEN_API_KEY", "NEXGEN_TIMEOUT"):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def fake_post(monkeypatch: pytest.MonkeyPatch) -> FakePost:
    """Replace requests.post in the actuators module, so no request is sent."""
    fake = FakePost()
    monkeypatch.setattr(actuators.requests, "post", fake)
    return fake


@pytest.fixture
def fake_get(monkeypatch: pytest.MonkeyPatch) -> FakePost:
    """Replace requests.get, so no request is sent."""
    fake = FakePost()
    fake.response = FakeResponse(status_code=200)
    monkeypatch.setattr(requests, "get", fake)
    return fake


@pytest.fixture
def fake_put(monkeypatch: pytest.MonkeyPatch) -> FakePost:
    """Replace requests.put, so no request is sent."""
    fake = FakePost()
    fake.response = FakeResponse(status_code=200)
    monkeypatch.setattr(requests, "put", fake)
    return fake


@pytest.fixture
def fake_delete(monkeypatch: pytest.MonkeyPatch) -> FakePost:
    """Replace requests.delete, so no request is sent."""
    fake = FakePost()
    fake.response = FakeResponse(status_code=204)
    monkeypatch.setattr(requests, "delete", fake)
    return fake
