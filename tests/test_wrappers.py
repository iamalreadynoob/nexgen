"""Tests for nexgenpy.wrappers."""

from datetime import UTC, datetime
from functools import partial
from typing import Any

import pydantic
import pytest
import requests

from nexgenpy.schema import ContentList, ContentOut, DataList, DataOut
from nexgenpy.wrappers import DEFAULT_BASE_URL, Content, Data

BASE_URL = "https://nexgen.example/api/v1"
DATA_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
ACTUATOR_ID = "11111111-2222-3333-4444-555555555555"
CONTENT_ID = "99999999-8888-7777-6666-555555555555"


def data_body(**overrides: Any) -> dict[str, Any]:
    """A DataOut response body."""
    return {
        "id": DATA_ID,
        "actuator_id": ACTUATOR_ID,
        "metadata": {"value": 4},
        "linked_resource": "s3://inputs/frame-001.png",
        "specs": {"snr_db": 10},
        "created_at": "2026-10-01T00:00:00Z",
        "updated_at": "2026-10-02T12:30:00Z",
        **overrides,
    }


def list_body(*items: dict[str, Any], total: int | None = None) -> dict[str, Any]:
    """A GET /data response body."""
    return {"total": len(items) if total is None else total, "data": list(items)}


@pytest.fixture(autouse=True)
def base_url(monkeypatch: pytest.MonkeyPatch) -> str:
    """Send every request to a known base URL instead of the default."""
    monkeypatch.setenv("NEXGEN_BASE_URL", BASE_URL)
    return BASE_URL


# (method, smallest valid kwargs, fixture that fakes its HTTP verb)
ENDPOINTS = [
    ("get_data_list", {}, "fake_get"),
    ("create_data", {"actuator_id": ACTUATOR_ID, "metadata": {"v": 1}}, "fake_post"),
    ("get_data", {"data_id": DATA_ID}, "fake_get"),
    ("update_data", {"data_id": DATA_ID, "specs": {"snr_db": 10}}, "fake_put"),
    ("delete_data", {"data_id": DATA_ID}, "fake_delete"),
]

# The methods that take a data_id; the tests pass it themselves
ID_ENDPOINTS = [
    ("get_data", {}, "fake_get"),
    ("update_data", {"specs": {"snr_db": 10}}, "fake_put"),
    ("delete_data", {}, "fake_delete"),
]


def fake_for(request: pytest.FixtureRequest, method: str, fake_name: str):
    """Get the fake for a method, preloaded with a valid response body."""
    fake = request.getfixturevalue(fake_name)
    if method == "get_data_list":
        fake.response.payload = list_body(data_body())
    elif method != "delete_data":
        fake.response.payload = data_body()
    return fake


@pytest.fixture(params=ENDPOINTS, ids=[e[0] for e in ENDPOINTS])
def endpoint(request: pytest.FixtureRequest):
    """Each Data method with valid arguments, and the fake it sends to."""
    method, kwargs, fake_name = request.param
    send = partial(getattr(Data, method), **kwargs)
    return send, fake_for(request, method, fake_name)


@pytest.fixture(params=ID_ENDPOINTS, ids=[e[0] for e in ID_ENDPOINTS])
def id_endpoint(request: pytest.FixtureRequest):
    """Like endpoint, for the methods that take a data_id."""
    method, kwargs, fake_name = request.param
    send = partial(getattr(Data, method), **kwargs)
    return send, fake_for(request, method, fake_name)


# --- behaviour shared by every method --------------------------------------


def test_base_url_from_environment(endpoint):
    send, fake = endpoint
    send()
    assert fake.last["url"].startswith(f"{BASE_URL}/data")


def test_base_url_falls_back_to_default(endpoint, monkeypatch):
    monkeypatch.delenv("NEXGEN_BASE_URL")
    send, fake = endpoint
    send()
    assert fake.last["url"].startswith(f"{DEFAULT_BASE_URL}/data")


@pytest.mark.parametrize(
    ("method", "kwargs", "fake_name"),
    ENDPOINTS,
    ids=[e[0] for e in ENDPOINTS],
)
def test_method_can_be_called_on_an_instance(request, method, kwargs, fake_name):
    fake = fake_for(request, method, fake_name)
    getattr(Data(), method)(**kwargs)
    assert len(fake.calls) == 1


def test_api_key_header_from_environment(endpoint, monkeypatch):
    monkeypatch.setenv("NEXGEN_API_KEY", "secret")
    send, fake = endpoint
    send()
    assert fake.last["headers"]["X-API-KEY"] == "secret"


def test_no_api_key_sends_no_key(endpoint):
    send, fake = endpoint
    send()
    # requests drops headers whose value is None
    assert fake.last["headers"].get("X-API-KEY") is None


def test_default_timeout(endpoint):
    send, fake = endpoint
    send()
    assert fake.last["timeout"] == 60


def test_timeout_is_passed_through(endpoint):
    send, fake = endpoint
    send(timeout=5)
    assert fake.last["timeout"] == 5


@pytest.mark.parametrize("timeout", ["60", 1.5, None])
def test_invalid_timeout_raises_before_request(endpoint, timeout: Any):
    send, fake = endpoint
    with pytest.raises(ValueError, match="Timeout is invalid"):
        send(timeout=timeout)
    assert fake.calls == []


def test_invalid_argument_is_logged(endpoint, caplog: pytest.LogCaptureFixture):
    send, _ = endpoint
    with pytest.raises(ValueError):
        send(timeout="60")
    assert "Timeout is invalid" in caplog.text


def test_http_error_is_raised(endpoint):
    send, fake = endpoint
    fake.response = type(fake.response)(status_code=500)
    with pytest.raises(requests.HTTPError):
        send()


def test_connection_error_propagates(endpoint):
    send, fake = endpoint
    fake.error = requests.ConnectionError("connection refused")
    with pytest.raises(requests.ConnectionError):
        send()


# --- data_id handling (get_data, update_data, delete_data) -------------------


def test_data_id_is_in_url(id_endpoint):
    send, fake = id_endpoint
    send(data_id=DATA_ID)
    assert fake.last["url"] == f"{BASE_URL}/data/{DATA_ID}"


@pytest.mark.parametrize(
    ("data_id", "escaped"),
    [
        ("a/b", "a%2Fb"),
        ("../actuators/doubler", "..%2Factuators%2Fdoubler"),
        ("abc?limit=1", "abc%3Flimit%3D1"),
        ("abc#x", "abc%23x"),
        ("a b", "a%20b"),
    ],
)
def test_data_id_is_escaped(id_endpoint, data_id: str, escaped: str):
    send, fake = id_endpoint
    send(data_id=data_id)
    assert fake.last["url"] == f"{BASE_URL}/data/{escaped}"


@pytest.mark.parametrize("data_id", [123, None, b"id"])
def test_invalid_data_id_raises_before_request(id_endpoint, data_id: Any):
    send, fake = id_endpoint
    with pytest.raises(ValueError, match="data_id is invalid"):
        send(data_id=data_id)
    assert fake.calls == []


@pytest.mark.parametrize("data_id", ["", ".", ".."])
def test_path_segment_data_id_is_rejected(id_endpoint, data_id: str):
    """quote() keeps ".", so these would leave /data/{data_id}."""
    send, fake = id_endpoint
    with pytest.raises(ValueError, match="data_id is invalid"):
        send(data_id=data_id)
    assert fake.calls == []


# --- get_data_list -------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("page", "1", "Page is invalid"),
        ("page", 1.0, "Page is invalid"),
        ("limit", "10", "Limit is invalid"),
        ("ascending", "yes", "Ascending is invalid"),
        ("ascending", 1, "Ascending is invalid"),
        ("actuator_id", 123, "Actuator ID is invalid"),
    ],
)
def test_get_data_list_invalid_arguments_raise(
    fake_get,
    field: str,
    value: Any,
    message: str,
):
    with pytest.raises(ValueError, match=message):
        Data.get_data_list(**{field: value})
    assert fake_get.calls == []


def test_get_data_list_sends_no_params_by_default(fake_get):
    fake_get.response.payload = list_body()
    Data.get_data_list()
    assert fake_get.last["url"] == f"{BASE_URL}/data"
    assert fake_get.last["params"] == {}


def test_get_data_list_sends_given_params(fake_get):
    fake_get.response.payload = list_body()
    Data.get_data_list(page=2, limit=10, ascending=True, actuator_id=ACTUATOR_ID)
    assert fake_get.last["params"] == {
        "page": 2,
        "limit": 10,
        "ascending": True,
        "actuator_id": ACTUATOR_ID,
    }


def test_get_data_list_sends_falsy_params(fake_get):
    """0 and False are real values, not "not given"."""
    fake_get.response.payload = list_body()
    Data.get_data_list(page=0, ascending=False)
    assert fake_get.last["params"] == {"page": 0, "ascending": False}


def test_get_data_list_parses_response(fake_get):
    fake_get.response.payload = list_body(
        data_body(),
        data_body(id="other", linked_resource=None, specs=None),
        total=42,
    )

    result = Data.get_data_list()

    assert isinstance(result, DataList)
    assert result.total == 42
    assert all(isinstance(item, DataOut) for item in result.data)
    assert [item.id for item in result.data] == [DATA_ID, "other"]
    assert result.data[1].linked_resource is None
    assert result.data[1].specs is None


def test_get_data_list_empty_page(fake_get):
    fake_get.response.payload = list_body(total=3)
    result = Data.get_data_list(page=5)
    assert result.total == 3
    assert result.data == []


# --- create_data -------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("actuator_id", 123, "Actuator ID is invalid"),
        ("actuator_id", None, "Actuator ID is invalid"),
        ("metadata", None, "Metadata is invalid"),
        ("linked_resource", 5, "Linked Resource is invalid"),
        ("specs", "snr_db=10", "Specs is invalid"),
        ("specs", [("snr_db", 10)], "Specs is invalid"),
    ],
)
def test_create_data_invalid_arguments_raise(
    fake_post,
    field: str,
    value: Any,
    message: str,
):
    kwargs = {"actuator_id": ACTUATOR_ID, "metadata": {"value": 4}, field: value}
    with pytest.raises(ValueError, match=message):
        Data.create_data(**kwargs)
    assert fake_post.calls == []


def test_create_data_sends_body(fake_post):
    fake_post.response.payload = data_body()

    Data.create_data(
        actuator_id=ACTUATOR_ID,
        metadata={"value": 4},
        linked_resource="s3://inputs/frame-001.png",
        specs={"snr_db": 10},
    )

    assert fake_post.last["url"] == f"{BASE_URL}/data"
    assert fake_post.last["json"] == {
        "actuator_id": ACTUATOR_ID,
        "metadata": {"value": 4},
        "linked_resource": "s3://inputs/frame-001.png",
        "specs": {"snr_db": 10},
    }


def test_create_data_sends_null_for_omitted_fields(fake_post):
    """DataCreate requires linked_resource and specs, so they go as null."""
    fake_post.response.payload = data_body(linked_resource=None, specs=None)
    Data.create_data(actuator_id=ACTUATOR_ID, metadata=[1, 2, 3])
    assert fake_post.last["json"] == {
        "actuator_id": ACTUATOR_ID,
        "metadata": [1, 2, 3],
        "linked_resource": None,
        "specs": None,
    }


@pytest.mark.parametrize("metadata", [0, False, "", [], {}])
def test_create_data_accepts_falsy_metadata(fake_post, metadata: Any):
    fake_post.response.payload = data_body(metadata=metadata)
    result = Data.create_data(actuator_id=ACTUATOR_ID, metadata=metadata)
    assert fake_post.last["json"]["metadata"] == metadata
    assert result.metadata == metadata


def test_create_data_returns_created_item(fake_post):
    fake_post.response.payload = data_body()
    result = Data.create_data(actuator_id=ACTUATOR_ID, metadata={"value": 4})
    assert isinstance(result, DataOut)
    assert result.id == DATA_ID


# --- get_data ----------------------------------------------------------------


def test_get_data_returns_item(fake_get):
    fake_get.response.payload = data_body()

    result = Data.get_data(DATA_ID)

    assert isinstance(result, DataOut)
    assert result.model_dump() == {
        "id": DATA_ID,
        "actuator_id": ACTUATOR_ID,
        "metadata": {"value": 4},
        "linked_resource": "s3://inputs/frame-001.png",
        "specs": {"snr_db": 10},
        "created_at": datetime(2026, 10, 1, tzinfo=UTC),
        "updated_at": datetime(2026, 10, 2, 12, 30, tzinfo=UTC),
    }


def test_get_data_unknown_id_raises(fake_get):
    fake_get.response = type(fake_get.response)(status_code=404)
    with pytest.raises(requests.HTTPError):
        Data.get_data("missing")


def test_get_data_malformed_response_raises(fake_get):
    fake_get.response.payload = {"id": DATA_ID}
    with pytest.raises(pydantic.ValidationError):
        Data.get_data(DATA_ID)


# --- update_data -------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("linked_resource", 5, "Linked Resource is invalid"),
        ("specs", "snr_db=10", "Specs is invalid"),
        ("specs", [("snr_db", 10)], "Specs is invalid"),
    ],
)
def test_update_data_invalid_arguments_raise(
    fake_put,
    field: str,
    value: Any,
    message: str,
):
    with pytest.raises(ValueError, match=message):
        Data.update_data(DATA_ID, **{field: value})
    assert fake_put.calls == []


@pytest.mark.parametrize(
    ("kwargs", "body"),
    [
        ({}, {}),
        ({"linked_resource": "s3://x"}, {"linked_resource": "s3://x"}),
        ({"specs": {"snr_db": 3}}, {"specs": {"snr_db": 3}}),
        (
            {"linked_resource": "s3://x", "specs": {"snr_db": 3}},
            {"linked_resource": "s3://x", "specs": {"snr_db": 3}},
        ),
    ],
    ids=["nothing", "linked_resource", "specs", "both"],
)
def test_update_data_sends_only_given_fields(
    fake_put,
    kwargs: dict[str, Any],
    body: dict[str, Any],
):
    fake_put.response.payload = data_body()
    Data.update_data(DATA_ID, **kwargs)
    assert fake_put.last["json"] == body


def test_update_data_sends_empty_values(fake_put):
    """An empty string and an empty dict are values to store, not "not given"."""
    fake_put.response.payload = data_body(linked_resource="", specs={})
    Data.update_data(DATA_ID, linked_resource="", specs={})
    assert fake_put.last["json"] == {"linked_resource": "", "specs": {}}


def test_update_data_returns_updated_item(fake_put):
    fake_put.response.payload = data_body(specs={"snr_db": 3})
    result = Data.update_data(DATA_ID, specs={"snr_db": 3})
    assert isinstance(result, DataOut)
    assert result.specs == {"snr_db": 3}


# --- delete_data -------------------------------------------------------------


def test_delete_data_returns_none(fake_delete):
    assert Data.delete_data(DATA_ID) is None
    assert len(fake_delete.calls) == 1


def test_delete_data_ignores_response_body(fake_delete):
    fake_delete.response = type(fake_delete.response)(status_code=200, payload="ok")
    assert Data.delete_data(DATA_ID) is None


# === Content ==================================================================


def content_body(**overrides: Any) -> dict[str, Any]:
    """A ContentOut response body."""
    return {
        "id": CONTENT_ID,
        "identifier": "frame-001",
        "specs": {"resolution": "1080p"},
        "created_at": "2026-10-01T00:00:00Z",
        "updated_at": "2026-10-02T12:30:00Z",
        **overrides,
    }


# (method, smallest valid kwargs, fixture that fakes its HTTP verb)
CONTENT_ENDPOINTS = [
    ("get_content_list", {}, "fake_get"),
    ("create_content", {"identifier": "frame-001"}, "fake_post"),
    ("get_content", {"content_id": CONTENT_ID}, "fake_get"),
    ("update_specs", {"content_id": CONTENT_ID, "specs": {"a": 1}}, "fake_put"),
    ("delete_content", {"content_id": CONTENT_ID}, "fake_delete"),
]

# The methods that take a content_id; the tests pass it themselves.
# (method, other kwargs, fake fixture, URL part after /contents/{content_id})
CONTENT_ID_ENDPOINTS = [
    ("get_content", {}, "fake_get", ""),
    ("update_specs", {"specs": {"a": 1}}, "fake_put", "/specs"),
    ("delete_content", {}, "fake_delete", ""),
]


def content_fake_for(request: pytest.FixtureRequest, method: str, fake_name: str):
    """Get the fake for a Content method, preloaded with a valid response body."""
    fake = request.getfixturevalue(fake_name)
    if method == "get_content_list":
        fake.response.payload = list_body(content_body())
    elif method != "delete_content":
        fake.response.payload = content_body()
    return fake


@pytest.fixture(params=CONTENT_ENDPOINTS, ids=[e[0] for e in CONTENT_ENDPOINTS])
def content_endpoint(request: pytest.FixtureRequest):
    """Each Content method with valid arguments, and the fake it sends to."""
    method, kwargs, fake_name = request.param
    send = partial(getattr(Content, method), **kwargs)
    return send, content_fake_for(request, method, fake_name)


@pytest.fixture(
    params=CONTENT_ID_ENDPOINTS,
    ids=[e[0] for e in CONTENT_ID_ENDPOINTS],
)
def content_id_endpoint(request: pytest.FixtureRequest):
    """Like content_endpoint, for the methods that take a content_id."""
    method, kwargs, fake_name, suffix = request.param
    send = partial(getattr(Content, method), **kwargs)
    return send, content_fake_for(request, method, fake_name), suffix


# --- behaviour shared by every Content method --------------------------------


def test_content_base_url_from_environment(content_endpoint):
    send, fake = content_endpoint
    send()
    assert fake.last["url"].startswith(f"{BASE_URL}/contents")


def test_content_base_url_falls_back_to_default(content_endpoint, monkeypatch):
    monkeypatch.delenv("NEXGEN_BASE_URL")
    send, fake = content_endpoint
    send()
    assert fake.last["url"].startswith(f"{DEFAULT_BASE_URL}/contents")


@pytest.mark.parametrize(
    ("method", "kwargs", "fake_name"),
    CONTENT_ENDPOINTS,
    ids=[e[0] for e in CONTENT_ENDPOINTS],
)
def test_content_method_can_be_called_on_an_instance(
    request,
    method,
    kwargs,
    fake_name,
):
    fake = content_fake_for(request, method, fake_name)
    getattr(Content(), method)(**kwargs)
    assert len(fake.calls) == 1


def test_content_api_key_header_from_environment(content_endpoint, monkeypatch):
    monkeypatch.setenv("NEXGEN_API_KEY", "secret")
    send, fake = content_endpoint
    send()
    assert fake.last["headers"]["X-API-KEY"] == "secret"


def test_content_no_api_key_sends_no_key(content_endpoint):
    send, fake = content_endpoint
    send()
    # requests drops headers whose value is None
    assert fake.last["headers"].get("X-API-KEY") is None


def test_content_default_timeout(content_endpoint):
    send, fake = content_endpoint
    send()
    assert fake.last["timeout"] == 60


def test_content_timeout_is_passed_through(content_endpoint):
    send, fake = content_endpoint
    send(timeout=5)
    assert fake.last["timeout"] == 5


@pytest.mark.parametrize("timeout", ["60", 1.5, None])
def test_content_invalid_timeout_raises_before_request(
    content_endpoint,
    timeout: Any,
):
    send, fake = content_endpoint
    with pytest.raises(ValueError, match="Timeout is invalid"):
        send(timeout=timeout)
    assert fake.calls == []


def test_content_invalid_argument_is_logged(
    content_endpoint,
    caplog: pytest.LogCaptureFixture,
):
    send, _ = content_endpoint
    with pytest.raises(ValueError):
        send(timeout="60")
    assert "Timeout is invalid" in caplog.text


def test_content_http_error_is_raised(content_endpoint):
    send, fake = content_endpoint
    fake.response = type(fake.response)(status_code=500)
    with pytest.raises(requests.HTTPError):
        send()


def test_content_connection_error_propagates(content_endpoint):
    send, fake = content_endpoint
    fake.error = requests.ConnectionError("connection refused")
    with pytest.raises(requests.ConnectionError):
        send()


# --- content_id handling (get_content, update_specs, delete_content) ---------


def test_content_id_is_in_url(content_id_endpoint):
    send, fake, suffix = content_id_endpoint
    send(content_id=CONTENT_ID)
    assert fake.last["url"] == f"{BASE_URL}/contents/{CONTENT_ID}{suffix}"


@pytest.mark.parametrize(
    ("content_id", "escaped"),
    [
        ("a/b", "a%2Fb"),
        ("../actuators/doubler", "..%2Factuators%2Fdoubler"),
        ("abc?limit=1", "abc%3Flimit%3D1"),
        ("abc#x", "abc%23x"),
        ("a b", "a%20b"),
    ],
)
def test_content_id_is_escaped(content_id_endpoint, content_id: str, escaped: str):
    send, fake, suffix = content_id_endpoint
    send(content_id=content_id)
    assert fake.last["url"] == f"{BASE_URL}/contents/{escaped}{suffix}"


@pytest.mark.parametrize("content_id", [123, None, b"id"])
def test_invalid_content_id_raises_before_request(
    content_id_endpoint,
    content_id: Any,
):
    send, fake, _ = content_id_endpoint
    with pytest.raises(ValueError, match="content_id is invalid"):
        send(content_id=content_id)
    assert fake.calls == []


@pytest.mark.parametrize("content_id", ["", ".", ".."])
def test_path_segment_content_id_is_rejected(content_id_endpoint, content_id: str):
    """quote() keeps ".", so these would leave /contents/{content_id}."""
    send, fake, _ = content_id_endpoint
    with pytest.raises(ValueError, match="content_id is invalid"):
        send(content_id=content_id)
    assert fake.calls == []


# --- get_content_list ----------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("page", "1", "Page is invalid"),
        ("page", 1.0, "Page is invalid"),
        ("limit", "10", "Limit is invalid"),
        ("ascending", "yes", "Ascending is invalid"),
        ("ascending", 1, "Ascending is invalid"),
        ("actuator_id", 123, "Actuator ID is invalid"),
    ],
)
def test_get_content_list_invalid_arguments_raise(
    fake_get,
    field: str,
    value: Any,
    message: str,
):
    with pytest.raises(ValueError, match=message):
        Content.get_content_list(**{field: value})
    assert fake_get.calls == []


def test_get_content_list_sends_no_params_by_default(fake_get):
    fake_get.response.payload = list_body()
    Content.get_content_list()
    assert fake_get.last["url"] == f"{BASE_URL}/contents"
    assert fake_get.last["params"] == {}


def test_get_content_list_sends_given_params(fake_get):
    fake_get.response.payload = list_body()
    Content.get_content_list(
        page=2,
        limit=10,
        ascending=True,
        actuator_id=ACTUATOR_ID,
    )
    assert fake_get.last["params"] == {
        "page": 2,
        "limit": 10,
        "ascending": True,
        "actuator_id": ACTUATOR_ID,
    }


def test_get_content_list_sends_falsy_params(fake_get):
    """0 and False are real values, not "not given"."""
    fake_get.response.payload = list_body()
    Content.get_content_list(page=0, ascending=False)
    assert fake_get.last["params"] == {"page": 0, "ascending": False}


def test_get_content_list_parses_response(fake_get):
    fake_get.response.payload = list_body(
        content_body(),
        content_body(id="other", specs=None),
        total=42,
    )

    result = Content.get_content_list()

    assert isinstance(result, ContentList)
    assert result.total == 42
    assert all(isinstance(item, ContentOut) for item in result.data)
    assert [item.id for item in result.data] == [CONTENT_ID, "other"]
    assert result.data[1].specs is None


def test_get_content_list_empty_page(fake_get):
    fake_get.response.payload = list_body(total=3)
    result = Content.get_content_list(page=5)
    assert result.total == 3
    assert result.data == []


def test_get_content_list_malformed_item_raises(fake_get):
    fake_get.response.payload = list_body({"id": CONTENT_ID})
    with pytest.raises(pydantic.ValidationError):
        Content.get_content_list()


# --- create_content ------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("identifier", 123, "Identifier is invalid"),
        ("identifier", None, "Identifier is invalid"),
        ("specs", "resolution=1080p", "Specs is invalid"),
        ("specs", [("resolution", "1080p")], "Specs is invalid"),
    ],
)
def test_create_content_invalid_arguments_raise(
    fake_post,
    field: str,
    value: Any,
    message: str,
):
    kwargs = {"identifier": "frame-001", field: value}
    with pytest.raises(ValueError, match=message):
        Content.create_content(**kwargs)
    assert fake_post.calls == []


def test_create_content_sends_body(fake_post):
    fake_post.response.payload = content_body()

    Content.create_content(identifier="frame-001", specs={"resolution": "1080p"})

    assert fake_post.last["url"] == f"{BASE_URL}/contents"
    assert fake_post.last["json"] == {
        "identifier": "frame-001",
        "specs": {"resolution": "1080p"},
    }


def test_create_content_sends_null_for_omitted_specs(fake_post):
    fake_post.response.payload = content_body(specs=None)
    Content.create_content(identifier="frame-001")
    assert fake_post.last["json"] == {"identifier": "frame-001", "specs": None}


def test_create_content_sends_empty_specs(fake_post):
    """An empty dict is a value to store, not "not given"."""
    fake_post.response.payload = content_body(specs={})
    result = Content.create_content(identifier="frame-001", specs={})
    assert fake_post.last["json"]["specs"] == {}
    assert result.specs == {}


def test_create_content_returns_created_item(fake_post):
    fake_post.response.payload = content_body()
    result = Content.create_content(identifier="frame-001")
    assert isinstance(result, ContentOut)
    assert result.id == CONTENT_ID
    assert result.identifier == "frame-001"


# --- get_content ---------------------------------------------------------------


def test_get_content_returns_item(fake_get):
    fake_get.response.payload = content_body()

    result = Content.get_content(CONTENT_ID)

    assert isinstance(result, ContentOut)
    assert result.model_dump() == {
        "id": CONTENT_ID,
        "identifier": "frame-001",
        "specs": {"resolution": "1080p"},
        "created_at": datetime(2026, 10, 1, tzinfo=UTC),
        "updated_at": datetime(2026, 10, 2, 12, 30, tzinfo=UTC),
    }


def test_get_content_unknown_id_raises(fake_get):
    fake_get.response = type(fake_get.response)(status_code=404)
    with pytest.raises(requests.HTTPError):
        Content.get_content("missing")


def test_get_content_malformed_response_raises(fake_get):
    fake_get.response.payload = {"id": CONTENT_ID}
    with pytest.raises(pydantic.ValidationError):
        Content.get_content(CONTENT_ID)


# --- update_specs --------------------------------------------------------------


@pytest.mark.parametrize("specs", [None, "resolution=1080p", [("a", 1)]])
def test_update_specs_invalid_specs_raise(fake_put, specs: Any):
    with pytest.raises(ValueError, match="Specs is invalid"):
        Content.update_specs(CONTENT_ID, specs=specs)
    assert fake_put.calls == []


def test_update_specs_sends_body(fake_put):
    fake_put.response.payload = content_body(specs={"resolution": "4k"})
    Content.update_specs(CONTENT_ID, specs={"resolution": "4k"})
    assert fake_put.last["url"] == f"{BASE_URL}/contents/{CONTENT_ID}/specs"
    assert fake_put.last["json"] == {"specs": {"resolution": "4k"}}


def test_update_specs_sends_empty_specs(fake_put):
    """An empty dict is a value to store, not "not given"."""
    fake_put.response.payload = content_body(specs={})
    Content.update_specs(CONTENT_ID, specs={})
    assert fake_put.last["json"] == {"specs": {}}


def test_update_specs_returns_updated_item(fake_put):
    fake_put.response.payload = content_body(specs={"resolution": "4k"})
    result = Content.update_specs(CONTENT_ID, specs={"resolution": "4k"})
    assert isinstance(result, ContentOut)
    assert result.specs == {"resolution": "4k"}


# --- delete_content ------------------------------------------------------------


def test_delete_content_returns_none(fake_delete):
    assert Content.delete_content(CONTENT_ID) is None
    assert len(fake_delete.calls) == 1
    assert fake_delete.last["url"] == f"{BASE_URL}/contents/{CONTENT_ID}"


def test_delete_content_ignores_response_body(fake_delete):
    fake_delete.response = type(fake_delete.response)(status_code=200, payload="ok")
    assert Content.delete_content(CONTENT_ID) is None
