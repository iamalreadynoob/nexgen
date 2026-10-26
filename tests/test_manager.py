"""Tests for nexgenpy.manager."""

import asyncio
import json
import os
import shutil
import sys
import textwrap
import threading
import time
import types
import uuid
from pathlib import Path
from typing import Any

import pytest
import requests

from nexgenpy import manager
from nexgenpy.manager import (
    DEFAULT_BASE_URL,
    Actuator,
    _send_content,
    load_actuator,
    run_actuator,
)

ACTUATOR_ID = "11111111-2222-3333-4444-555555555555"

METHOD_SOURCE = """\
def double(x: int, factor: int = 2) -> dict:
    return {"value": x * factor}
"""


def api_response(**overrides: Any) -> dict[str, Any]:
    """A GET /actuators/{name}/latest response body."""
    return {
        "_id": ACTUATOR_ID,
        "name": "doubler",
        "version": "1.0.0",
        "actuator_type": "coding",
        "method_args": {"x": {"type": "<class 'int'>"}},
        "latest": True,
        "created_at": "2026-10-01T00:00:00Z",
        "updated_at": "2026-10-01T00:00:00Z",
        "requirements": ["numpy==2.0.0", "pandas"],
        "method": METHOD_SOURCE,
        **overrides,
    }


def write_actuator(
    actuators_dir: Path,
    name: str = "doubler",
    method: str = METHOD_SOURCE,
    card: dict[str, Any] | None = None,
) -> Path:
    """Create an already-loaded actuator on disk, like load_actuator does."""
    directory = actuators_dir / name
    directory.mkdir(parents=True)
    (directory / "method.py").write_text(textwrap.dedent(method))
    (directory / "requirements.txt").write_text("")
    # A fake venv: its python is the test interpreter, so no venv is built
    if os.name == "nt":
        python = directory / ".venv" / "Scripts" / "python.exe"
    else:
        python = directory / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.symlink_to(sys.executable)
    # The Windows venv launcher does not follow the symlink: it looks for
    # pyvenv.cfg next to its own path, so give the fake venv a copy
    venv_cfg = Path(sys.prefix) / "pyvenv.cfg"
    if os.name == "nt" and venv_cfg.is_file():
        shutil.copy(venv_cfg, directory / ".venv" / "pyvenv.cfg")
    if card is None:
        card = {"id": ACTUATOR_ID, "name": name, "version": "1.0.0"}
    (directory / "card.json").write_text(json.dumps(card))
    return directory


@pytest.fixture
def actuators_dir(tmp_path: Path) -> Path:
    return tmp_path / "nexgen_actuators"


@pytest.fixture
def sync_threads(monkeypatch) -> list[dict[str, Any]]:
    """Run the lazy content upload in the calling thread.

    Only the manager's reference to threading is replaced, so asyncio.to_thread
    keeps working. Other threads, like the stderr reader of the Actuator
    workers, still run in a real thread. It returns the kwargs of every started
    upload thread.
    """
    started: list[dict[str, Any]] = []
    real_thread = threading.Thread

    class SyncThread:
        def __init__(
            self,
            target: Any,
            kwargs: dict[str, Any] | None = None,
            **options: Any,
        ) -> None:
            self.target = target
            self.kwargs = kwargs or {}
            self.options = options
            self.thread: threading.Thread | None = None

        def start(self) -> None:
            if self.target is not manager._send_content:
                self.thread = real_thread(
                    target=self.target,
                    kwargs=self.kwargs,
                    **self.options,
                )
                self.thread.start()
                return
            started.append(self.kwargs)
            self.target(**self.kwargs)

        def join(self, timeout: float | None = None) -> None:
            # _Worker joins its stderr reader when the worker crashes
            if self.thread is not None:
                self.thread.join(timeout)

    monkeypatch.setattr(manager, "threading", types.SimpleNamespace(Thread=SyncThread))
    return started


@pytest.fixture
def fake_subprocess(monkeypatch) -> list[list[str]]:
    """Record the venv / pip commands instead of running them."""
    commands: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: Any) -> None:
        assert kwargs.get("check") is True
        commands.append(cmd)

    monkeypatch.setattr(manager.subprocess, "run", fake_run)
    return commands


def calls_to(fake_post, suffix: str) -> list[dict[str, Any]]:
    return [c for c in fake_post.calls if c["url"].endswith(suffix)]


# ===========================================================================
# load_actuator
# ===========================================================================


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", 1),
        ("actuators_dir", Path("x")),
        ("load_timeout", 1.5),
        ("update_actuator", "yes"),
    ],
)
def test_load_invalid_arguments(actuators_dir, field: str, value: Any):
    kwargs = {"name": "doubler", "actuators_dir": str(actuators_dir), field: value}
    with pytest.raises(ValueError, match=field):
        load_actuator(**kwargs)


@pytest.mark.parametrize("name", ["", ".", "..", "../evil", "a/b", "/etc"])
def test_load_rejects_names_outside_actuators_dir(fake_get, actuators_dir, name):
    with pytest.raises(ValueError, match="plain directory name"):
        load_actuator(name, actuators_dir=str(actuators_dir))
    assert fake_get.calls == []


@pytest.mark.usefixtures("fake_subprocess")
def test_load_writes_actuator_files(fake_get, actuators_dir):
    fake_get.response.payload = api_response()

    load_actuator("doubler", actuators_dir=str(actuators_dir))

    directory = actuators_dir / "doubler"
    assert (directory / "method.py").read_text() == METHOD_SOURCE
    assert (directory / "requirements.txt").read_text() == "numpy==2.0.0\npandas"

    card = json.loads((directory / "card.json").read_text())
    assert card == {
        "id": ACTUATOR_ID,
        "name": "doubler",
        "version": "1.0.0",
        "actuator_type": "coding",
        "method_args": {"x": {"type": "<class 'int'>"}},
        "latest": True,
        "created_at": "2026-10-01T00:00:00Z",
        "updated_at": "2026-10-01T00:00:00Z",
    }


def test_load_creates_venv_and_installs_requirements(
    fake_get,
    fake_subprocess,
    actuators_dir,
):
    fake_get.response.payload = api_response()
    directory = f"{actuators_dir}/doubler"

    load_actuator("doubler", actuators_dir=str(actuators_dir))

    pip = (
        f"{directory}/.venv/Scripts/pip.exe"
        if sys.platform == "win32"
        else f"{directory}/.venv/bin/pip"
    )
    assert fake_subprocess == [
        [sys.executable, "-m", "venv", f"{directory}/.venv"],
        [pip, "install", "-r", f"{directory}/requirements.txt"],
    ]


@pytest.mark.usefixtures("fake_subprocess")
def test_load_request_defaults(fake_get, actuators_dir):
    fake_get.response.payload = api_response()

    load_actuator("doubler", actuators_dir=str(actuators_dir))

    assert fake_get.last["url"] == f"{DEFAULT_BASE_URL}/actuators/doubler/latest"
    assert fake_get.last["headers"] == {}
    assert fake_get.last["timeout"] == 60


@pytest.mark.usefixtures("fake_subprocess")
def test_load_request_uses_environment_and_timeout(
    fake_get,
    actuators_dir,
    monkeypatch,
):
    monkeypatch.setenv("NEXGEN_BASE_URL", "https://nexgen.example/api")
    monkeypatch.setenv("NEXGEN_API_KEY", "secret")
    fake_get.response.payload = api_response()

    load_actuator("doubler", actuators_dir=str(actuators_dir), load_timeout=7)

    assert fake_get.last["url"] == "https://nexgen.example/api/actuators/doubler/latest"
    assert fake_get.last["headers"] == {"X-API-KEY": "secret"}
    assert fake_get.last["timeout"] == 7


@pytest.mark.usefixtures("fake_subprocess")
def test_load_uses_default_dir_relative_to_cwd(fake_get, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake_get.response.payload = api_response()

    load_actuator("doubler")

    assert (tmp_path / "nexgen_actuators" / "doubler" / "card.json").exists()


def test_load_http_error_raises_and_writes_nothing(
    fake_get,
    fake_subprocess,
    actuators_dir,
):
    fake_get.response = type(fake_get.response)(status_code=404)

    with pytest.raises(requests.HTTPError):
        load_actuator("doubler", actuators_dir=str(actuators_dir))

    assert not (actuators_dir / "doubler").exists()
    assert fake_subprocess == []


def test_load_skips_request_when_exists_and_update_disabled(
    fake_get,
    fake_subprocess,
    actuators_dir,
):
    write_actuator(actuators_dir)

    load_actuator("doubler", actuators_dir=str(actuators_dir), update_actuator=False)

    assert fake_get.calls == []
    assert fake_subprocess == []


def test_load_skips_when_already_up_to_date(fake_get, fake_subprocess, actuators_dir):
    directory = write_actuator(actuators_dir, method="def old():\n    return 1\n")
    fake_get.response.payload = api_response()

    load_actuator("doubler", actuators_dir=str(actuators_dir))

    assert len(fake_get.calls) == 1
    assert fake_subprocess == []
    assert (directory / "method.py").read_text() == "def old():\n    return 1\n"


@pytest.mark.parametrize(
    "changed",
    [{"version": "2.0.0"}, {"_id": "another-id"}],
)
def test_load_replaces_outdated_actuator(
    fake_get,
    fake_subprocess,
    actuators_dir,
    changed,
):
    directory = write_actuator(actuators_dir, method="def old():\n    return 1\n")
    (directory / "leftover.txt").write_text("stale")
    fake_get.response.payload = api_response(**changed)

    load_actuator("doubler", actuators_dir=str(actuators_dir))

    assert (directory / "method.py").read_text() == METHOD_SOURCE
    assert not (directory / "leftover.txt").exists()
    card = json.loads((directory / "card.json").read_text())
    assert card["version"] == changed.get("version", "1.0.0")
    assert card["id"] == changed.get("_id", ACTUATOR_ID)
    assert len(fake_subprocess) == 2


@pytest.mark.usefixtures("fake_subprocess")
def test_load_replaces_directory_without_card(fake_get, actuators_dir):
    directory = actuators_dir / "doubler"
    directory.mkdir(parents=True)
    (directory / "method.py").write_text("broken")
    fake_get.response.payload = api_response()

    load_actuator("doubler", actuators_dir=str(actuators_dir))

    assert (directory / "method.py").read_text() == METHOD_SOURCE
    assert (directory / "card.json").exists()


def test_load_failed_install_leaves_no_card(fake_get, actuators_dir, monkeypatch):
    """A failed pip install must not look like an up-to-date actuator later."""
    fake_get.response.payload = api_response()

    def failing_run(cmd: list[str], **kwargs: Any) -> None:  # noqa: ARG001
        if "install" in cmd:
            raise manager.subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(manager.subprocess, "run", failing_run)

    with pytest.raises(manager.subprocess.CalledProcessError):
        load_actuator("doubler", actuators_dir=str(actuators_dir))

    assert (actuators_dir / "doubler" / "method.py").exists()
    assert not (actuators_dir / "doubler" / "card.json").exists()


# ===========================================================================
# run_actuator
# ===========================================================================


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", None),
        ("data", [1]),
        ("data_specs", "specs"),
        ("actuators_dir", 5),
        ("dst", 5),
        ("dst_timeout", "60"),
        ("dst_headers", [("a", "b")]),
        ("dst_save_original", 1),
        ("try_load_actuator", None),
    ],
)
def test_run_invalid_arguments(actuators_dir, field: str, value: Any):
    kwargs: dict[str, Any] = {
        "name": "doubler",
        "data": {"x": 1},
        "actuators_dir": str(actuators_dir),
        field: value,
    }
    with pytest.raises(ValueError, match=field):
        run_actuator(**kwargs)


def test_run_returns_method_output(actuators_dir, fake_post):
    write_actuator(actuators_dir)

    output = run_actuator(
        "doubler",
        data={"x": 4, "factor": 3},
        actuators_dir=str(actuators_dir),
    )

    assert output == {"value": 12}
    assert fake_post.calls == []


def test_run_uses_default_dir_relative_to_cwd(tmp_path, monkeypatch):
    write_actuator(tmp_path / "nexgen_actuators")
    monkeypatch.chdir(tmp_path)

    assert run_actuator("doubler", data={"x": 1}) == {"value": 2}


def test_run_without_dst_does_not_need_card(actuators_dir):
    directory = write_actuator(actuators_dir)
    (directory / "card.json").unlink()

    assert run_actuator(
        "doubler",
        data={"x": 1},
        actuators_dir=str(actuators_dir),
    ) == {"value": 2}


def test_run_missing_actuator_without_loading_raises(actuators_dir, fake_get):
    with pytest.raises(ValueError, match="has to be downloaded first"):
        run_actuator(
            "doubler",
            data={"x": 1},
            actuators_dir=str(actuators_dir),
            try_load_actuator=False,
        )
    assert fake_get.calls == []


def test_run_loads_missing_actuator(actuators_dir, monkeypatch):
    loaded: list[dict[str, Any]] = []

    def fake_load(**kwargs: Any) -> None:
        loaded.append(kwargs)
        write_actuator(Path(kwargs["actuators_dir"]), name=kwargs["name"])

    monkeypatch.setattr(manager, "load_actuator", fake_load)

    output = run_actuator(
        "doubler",
        data={"x": 5},
        actuators_dir=str(actuators_dir),
    )

    assert output == {"value": 10}
    assert loaded == [{"name": "doubler", "actuators_dir": str(actuators_dir)}]


def test_run_ignores_imported_functions(actuators_dir):
    write_actuator(
        actuators_dir,
        method="""\
        from os.path import join


        def joiner(a, b):
            return join(a, b)
        """,
    )

    assert run_actuator(
        "doubler",
        data={"a": "x", "b": "y"},
        actuators_dir=str(actuators_dir),
    ) == os.path.join("x", "y")


@pytest.mark.parametrize(
    ("method", "count"),
    [
        ("VALUE = 1\n", 0),
        ("def a():\n    return 1\n\n\ndef b():\n    return 2\n", 2),
    ],
)
def test_run_requires_exactly_one_function(actuators_dir, method, count):
    write_actuator(actuators_dir, method=method)

    with pytest.raises(ValueError, match=f"exactly one function, found {count}"):
        run_actuator("doubler", data={}, actuators_dir=str(actuators_dir))


def test_run_propagates_method_errors(actuators_dir):
    write_actuator(actuators_dir)

    with pytest.raises(RuntimeError, match="TypeError"):
        run_actuator("doubler", data={"y": 1}, actuators_dir=str(actuators_dir))


@pytest.mark.usefixtures("sync_threads")
def test_run_with_dst_sends_output(actuators_dir, fake_post):
    write_actuator(actuators_dir)

    output = run_actuator(
        "doubler",
        data={"x": 2},
        data_specs={"source": "sensor-1"},
        actuators_dir=str(actuators_dir),
        dst="https://dst.example",
        dst_timeout=9,
        dst_headers={"Authorization": "Bearer t"},
    )

    assert output == {"value": 4}

    data_call = calls_to(fake_post, "/data")[0]
    assert data_call["url"] == "https://dst.example/data"
    assert data_call["headers"] == {"Authorization": "Bearer t"}
    assert data_call["timeout"] == 9

    payload = data_call["json"]
    assert payload["actuator_id"] == ACTUATOR_ID
    assert payload["metadata"] == {"value": 4}
    assert payload["specs"] == {"source": "sensor-1"}
    uuid.UUID(payload["linked_resource"])


def test_run_with_dst_uploads_original_data(actuators_dir, fake_post, sync_threads):
    write_actuator(actuators_dir)

    run_actuator(
        "doubler",
        data={"x": 2},
        actuators_dir=str(actuators_dir),
        dst="https://dst.example",
        dst_timeout=9,
    )

    assert len(sync_threads) == 1
    content_call = calls_to(fake_post, "/contents")[0]
    data_call = calls_to(fake_post, "/data")[0]

    assert content_call["url"] == "https://dst.example/contents"
    assert content_call["headers"] == {}
    assert content_call["timeout"] == 9
    assert content_call["json"] == {
        "identifier": data_call["json"]["linked_resource"],
        "specs": {"x": 2},
    }


def test_run_with_dst_without_saving_original(actuators_dir, fake_post, sync_threads):
    write_actuator(actuators_dir)

    run_actuator(
        "doubler",
        data={"x": 2},
        actuators_dir=str(actuators_dir),
        dst="https://dst.example",
        dst_save_original=False,
    )

    assert sync_threads == []
    assert calls_to(fake_post, "/contents") == []
    assert calls_to(fake_post, "/data")[0]["json"]["linked_resource"] is None


@pytest.mark.usefixtures("sync_threads")
def test_run_with_dst_error_status_still_returns_output(
    actuators_dir,
    fake_post,
    caplog,
):
    write_actuator(actuators_dir)
    fake_post.response.status_code = 500
    fake_post.response.ok = False

    output = run_actuator(
        "doubler",
        data={"x": 2},
        actuators_dir=str(actuators_dir),
        dst="https://dst.example",
        dst_save_original=False,
    )

    assert output == {"value": 4}
    assert "POST /data failed: status=500" in caplog.text


def test_run_lazy_upload_runs_in_background_thread(actuators_dir, fake_post):
    """Without the sync_threads fixture the upload happens in a real thread."""
    write_actuator(actuators_dir)

    run_actuator(
        "doubler",
        data={"x": 2},
        actuators_dir=str(actuators_dir),
        dst="https://dst.example",
    )

    for thread in manager.threading.enumerate():
        if thread is not manager.threading.current_thread():
            thread.join(timeout=5)

    assert len(calls_to(fake_post, "/contents")) == 1
    assert len(calls_to(fake_post, "/data")) == 1


# ===========================================================================
# _send_content
# ===========================================================================


def send_content() -> None:
    _send_content(
        url="https://dst.example/contents",
        headers={"h": "v"},
        timeout=3,
        identifier="abc",
        specs={"x": 1},
    )


def test_send_content_posts_payload(fake_post, caplog):
    caplog.set_level("INFO")
    send_content()

    assert fake_post.last == {
        "url": "https://dst.example/contents",
        "headers": {"h": "v"},
        "json": {"identifier": "abc", "specs": {"x": 1}},
        "timeout": 3,
    }
    assert "POST /contents succeeded" in caplog.text


def test_send_content_logs_error_status(fake_post, caplog):
    fake_post.response.status_code = 413
    fake_post.response.ok = False

    send_content()

    assert "POST /contents failed: status=413" in caplog.text


def test_send_content_swallows_request_errors(fake_post, caplog):
    fake_post.error = requests.Timeout("timed out")

    send_content()

    assert "POST /contents failed: timed out" in caplog.text


# ===========================================================================
# Actuator
# ===========================================================================


@pytest.fixture
def make_actuator():
    """Build Actuators and close them after the test, so no worker is left."""
    created: list[Actuator] = []

    def make(*args: Any, **kwargs: Any) -> Actuator:
        act = Actuator(*args, **kwargs)
        created.append(act)
        return act

    yield make

    for act in created:
        act.close()


def worker_procs(act: Actuator) -> list[Any]:
    return [worker._proc for worker in act._pool]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", 1),
        ("actuators_dir", None),
        ("dst", 1),
        ("dst_timeout", 1.0),
        ("dst_headers", "h"),
        ("dst_save_original", "no"),
        ("try_load_actuator", 0),
        ("workers", 0),
        ("workers", "2"),
    ],
)
def test_actuator_invalid_arguments(actuators_dir, field: str, value: Any):
    kwargs: dict[str, Any] = {
        "name": "doubler",
        "actuators_dir": str(actuators_dir),
        field: value,
    }
    with pytest.raises(ValueError, match=field):
        Actuator(**kwargs)


def test_actuator_attributes(actuators_dir, make_actuator):
    write_actuator(actuators_dir)

    act = make_actuator("doubler", actuators_dir=str(actuators_dir))

    assert act.name == "doubler"
    assert act.actuators_dir == str(actuators_dir)
    assert act.dst is None
    assert act.dst_timeout == 60
    assert act.dst_headers == {}
    assert act.dst_save_original is True
    assert act.actuator_id is None
    assert act.method_name == "double"
    assert act.workers == 1


def test_actuator_reads_id_only_with_dst(actuators_dir, make_actuator):
    write_actuator(actuators_dir)

    act = make_actuator(
        "doubler",
        actuators_dir=str(actuators_dir),
        dst="https://dst.example",
        dst_headers={"h": "v"},
    )

    assert act.actuator_id == ACTUATOR_ID
    assert act.dst_headers == {"h": "v"}


def test_actuator_with_dst_needs_card(actuators_dir):
    directory = write_actuator(actuators_dir)
    (directory / "card.json").unlink()

    with pytest.raises(FileNotFoundError):
        Actuator("doubler", actuators_dir=str(actuators_dir), dst="https://dst")


def test_actuator_missing_without_loading_raises(actuators_dir):
    with pytest.raises(ValueError, match="has to be downloaded first"):
        Actuator("doubler", actuators_dir=str(actuators_dir), try_load_actuator=False)


def test_actuator_loads_missing_actuator(actuators_dir, monkeypatch, make_actuator):
    def fake_load(**kwargs: Any) -> None:
        write_actuator(Path(kwargs["actuators_dir"]), name=kwargs["name"])

    monkeypatch.setattr(manager, "load_actuator", fake_load)

    act = make_actuator("doubler", actuators_dir=str(actuators_dir))

    assert act.run({"x": 3}) == {"value": 6}


def test_actuator_requires_exactly_one_function(actuators_dir):
    write_actuator(actuators_dir, method="def a():\n    pass\n\n\ndef b():\n    pass\n")

    with pytest.raises(ValueError, match="exactly one function, found 2"):
        Actuator("doubler", actuators_dir=str(actuators_dir))


def test_actuator_imports_method_only_once(actuators_dir, make_actuator):
    directory = write_actuator(actuators_dir)
    act = make_actuator("doubler", actuators_dir=str(actuators_dir))

    (directory / "method.py").write_text("def changed(x):\n    return x\n")

    assert act.run({"x": 2}) == {"value": 4}
    assert act.run({"x": 5}) == {"value": 10}


def test_actuator_runs_in_the_actuator_venv(actuators_dir, make_actuator):
    write_actuator(
        actuators_dir,
        method="""\
        def where():
            import sys

            return sys.executable
        """,
    )
    act = make_actuator("doubler", actuators_dir=str(actuators_dir))

    venv = actuators_dir / "doubler" / ".venv"
    assert act.run({}) == str(manager._venv_python(venv))


def test_actuator_method_print_does_not_break_protocol(actuators_dir, make_actuator):
    write_actuator(
        actuators_dir,
        method="""\
        def loud(x):
            print("hello from the actuator")
            return x + 1
        """,
    )
    act = make_actuator("doubler", actuators_dir=str(actuators_dir))

    assert act.run({"x": 1}) == 2
    assert act.run({"x": 2}) == 3


def test_actuator_method_error_keeps_worker_alive(actuators_dir, make_actuator):
    write_actuator(actuators_dir)
    act = make_actuator("doubler", actuators_dir=str(actuators_dir))
    procs = worker_procs(act)

    with pytest.raises(RuntimeError, match="TypeError"):
        act.run({"y": 1})

    assert act.run({"x": 1}) == {"value": 2}
    assert worker_procs(act) == procs


def test_actuator_unpicklable_output_keeps_worker_alive(actuators_dir, make_actuator):
    write_actuator(
        actuators_dir,
        method="""\
        def make(x):
            if x == 0:
                return lambda: x
            return x
        """,
    )
    act = make_actuator("doubler", actuators_dir=str(actuators_dir))

    with pytest.raises(RuntimeError, match="failed"):
        act.run({"x": 0})

    assert act.run({"x": 1}) == 1


def test_actuator_replaces_crashed_worker(actuators_dir, make_actuator):
    write_actuator(
        actuators_dir,
        method="""\
        def crash(x):
            import os

            if x == 0:
                os._exit(3)
            return x
        """,
    )
    act = make_actuator("doubler", actuators_dir=str(actuators_dir))
    old_proc = worker_procs(act)[0]

    with pytest.raises(RuntimeError, match="exit code 3"):
        act.run({"x": 0})

    assert act.run({"x": 5}) == 5
    assert len(act._pool) == 1
    assert worker_procs(act)[0] is not old_proc


def test_actuator_import_error_raises_and_leaves_no_worker(actuators_dir, monkeypatch):
    write_actuator(
        actuators_dir,
        method="""\
        import module_that_does_not_exist


        def f(x):
            return x
        """,
    )
    started: list[Any] = []
    real_worker = manager._Worker

    def tracking_worker(*args: Any) -> Any:
        worker = real_worker(*args)
        started.append(worker)
        return worker

    monkeypatch.setattr(manager, "_Worker", tracking_worker)

    with pytest.raises(RuntimeError, match="module_that_does_not_exist"):
        Actuator("doubler", actuators_dir=str(actuators_dir), workers=2)

    assert len(started) == 2
    assert all(worker._proc.poll() is not None for worker in started)


def test_actuator_close_stops_workers(actuators_dir):
    write_actuator(actuators_dir)
    act = Actuator("doubler", actuators_dir=str(actuators_dir), workers=2)
    procs = worker_procs(act)

    act.close()
    act.close()

    assert all(proc.poll() is not None for proc in procs)
    with pytest.raises(RuntimeError, match="closed"):
        act.run({"x": 1})


def test_actuator_context_manager_closes(actuators_dir):
    write_actuator(actuators_dir)

    with Actuator("doubler", actuators_dir=str(actuators_dir)) as act:
        assert act.run({"x": 1}) == {"value": 2}
        procs = worker_procs(act)

    assert all(proc.poll() is not None for proc in procs)


@pytest.mark.parametrize("runner", ["run", "arun"])
@pytest.mark.parametrize(
    ("data", "data_specs", "field"),
    [([1], None, "data"), ({"x": 1}, "specs", "data_specs")],
)
def test_actuator_run_invalid_arguments(
    actuators_dir,
    make_actuator,
    runner,
    data,
    data_specs,
    field,
):
    write_actuator(actuators_dir)
    act = make_actuator("doubler", actuators_dir=str(actuators_dir))

    with pytest.raises(ValueError, match=f"{field} is invalid"):
        result = getattr(act, runner)(data, data_specs)
        if asyncio.iscoroutine(result):
            asyncio.run(result)


def run_method(act: Actuator, runner: str, *args: Any, **kwargs: Any) -> object:
    """Call run or arun the same way, so both share the tests below."""
    result = getattr(act, runner)(*args, **kwargs)
    if runner == "arun":
        return asyncio.run(result)
    return result


@pytest.fixture(params=["run", "arun"])
def runner(request) -> str:
    return request.param


def test_actuator_run_without_dst(actuators_dir, make_actuator, fake_post, runner):
    write_actuator(actuators_dir)
    act = make_actuator("doubler", actuators_dir=str(actuators_dir))

    assert run_method(act, runner, {"x": 7}) == {"value": 14}
    assert fake_post.calls == []


@pytest.mark.usefixtures("sync_threads")
def test_actuator_run_with_dst(actuators_dir, make_actuator, fake_post, runner):
    write_actuator(actuators_dir)
    act = make_actuator(
        "doubler",
        actuators_dir=str(actuators_dir),
        dst="https://dst.example",
        dst_timeout=4,
        dst_headers={"h": "v"},
    )

    output = run_method(act, runner, {"x": 1}, {"unit": "m"})

    assert output == {"value": 2}

    data_call = calls_to(fake_post, "/data")[0]
    content_call = calls_to(fake_post, "/contents")[0]
    assert data_call["url"] == "https://dst.example/data"
    assert data_call["headers"] == {"h": "v"}
    assert data_call["timeout"] == 4
    assert data_call["json"]["actuator_id"] == ACTUATOR_ID
    assert data_call["json"]["metadata"] == {"value": 2}
    assert data_call["json"]["specs"] == {"unit": "m"}
    assert content_call["json"] == {
        "identifier": data_call["json"]["linked_resource"],
        "specs": {"x": 1},
    }


def test_actuator_run_with_dst_without_saving_original(
    actuators_dir,
    make_actuator,
    fake_post,
    sync_threads,
    runner,
):
    write_actuator(actuators_dir)
    act = make_actuator(
        "doubler",
        actuators_dir=str(actuators_dir),
        dst="https://dst.example",
        dst_save_original=False,
    )

    run_method(act, runner, {"x": 1})

    assert sync_threads == []
    assert calls_to(fake_post, "/contents") == []
    assert calls_to(fake_post, "/data")[0]["json"]["linked_resource"] is None


@pytest.mark.usefixtures("sync_threads")
def test_actuator_run_logs_failed_data_post(
    actuators_dir,
    make_actuator,
    fake_post,
    runner,
    caplog,
):
    write_actuator(actuators_dir)
    fake_post.response.status_code = 503
    fake_post.response.ok = False
    act = make_actuator("doubler", actuators_dir=str(actuators_dir), dst="https://d")

    assert run_method(act, runner, {"x": 1}) == {"value": 2}
    assert "POST /data failed: status=503" in caplog.text


@pytest.mark.usefixtures("sync_threads")
def test_actuator_runs_get_a_new_linked_resource_each_time(
    actuators_dir,
    make_actuator,
    fake_post,
):
    write_actuator(actuators_dir)
    act = make_actuator("doubler", actuators_dir=str(actuators_dir), dst="https://d")

    act.run({"x": 1})
    act.run({"x": 1})

    first, second = (c["json"]["linked_resource"] for c in calls_to(fake_post, "/data"))
    assert first != second


def test_actuator_arun_runs_concurrently(actuators_dir, make_actuator):
    write_actuator(
        actuators_dir,
        method="""\
        import time


        def slow(x):
            time.sleep(0.2)
            return x
        """,
    )
    act = make_actuator("doubler", actuators_dir=str(actuators_dir), workers=5)

    async def main() -> list[object]:
        return await asyncio.gather(*(act.arun({"x": i}) for i in range(5)))

    start = time.perf_counter()
    results = asyncio.run(main())
    elapsed = time.perf_counter() - start

    assert results == [0, 1, 2, 3, 4]
    assert elapsed < 0.2 * 5


def test_actuator_single_worker_runs_one_call_at_a_time(actuators_dir, make_actuator):
    write_actuator(
        actuators_dir,
        method="""\
        import time


        def slow(x):
            time.sleep(0.2)
            return x
        """,
    )
    act = make_actuator("doubler", actuators_dir=str(actuators_dir))

    async def main() -> list[object]:
        return await asyncio.gather(*(act.arun({"x": i}) for i in range(3)))

    start = time.perf_counter()
    results = asyncio.run(main())
    elapsed = time.perf_counter() - start

    assert sorted(results) == [0, 1, 2]
    assert elapsed >= 0.2 * 3


# ===========================================================================
# Integration: real venv + pip, only the HTTP call is faked
# ===========================================================================


@pytest.mark.integration
def test_load_and_run_end_to_end(fake_get, actuators_dir):
    fake_get.response.payload = api_response(requirements=[])

    load_actuator("doubler", actuators_dir=str(actuators_dir))

    directory = actuators_dir / "doubler"
    assert (directory / ".venv").is_dir()
    assert (directory / "card.json").exists()

    output = run_actuator(
        "doubler",
        data={"x": 21},
        actuators_dir=str(actuators_dir),
        try_load_actuator=False,
    )
    assert output == {"value": 42}


@pytest.mark.integration
def test_load_and_run_actuator_class_end_to_end(fake_get, actuators_dir):
    fake_get.response.payload = api_response(requirements=[])

    load_actuator("doubler", actuators_dir=str(actuators_dir))

    with Actuator("doubler", actuators_dir=str(actuators_dir), workers=2) as act:
        assert act.run({"x": 21}) == {"value": 42}
        assert asyncio.run(act.arun({"x": 1})) == {"value": 2}
