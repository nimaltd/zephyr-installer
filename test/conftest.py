"""Shared fixtures: a throwaway library repository and a throwaway Zephyr application."""

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

SRC = Path(__file__).resolve().parent.parent / "src"

# The package is the src folder itself, so it is loaded under its own name
# rather than found on sys.path, and before any test imports it.
if "zephyr_installer" not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        "zephyr_installer", SRC / "__init__.py", submodule_search_locations=[str(SRC)]
    )
    _package = importlib.util.module_from_spec(_spec)
    sys.modules["zephyr_installer"] = _package
    _spec.loader.exec_module(_package)

from zephyr_installer.core import cli, download, target  # noqa: E402

CMAKELISTS = """cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(app)

target_sources(app PRIVATE src/main.c)
"""


@pytest.fixture(autouse=True)
def fresh_run():
    """Each test is a run of its own: no --conf, no answer and no file chosen yet."""
    zephyr = target.current
    zephyr.conf_given = None
    zephyr.conf_chosen = None
    zephyr.ask = None
    zephyr.conf_of = {}

    yield zephyr


@pytest.fixture
def library(tmp_path):
    """
    Build a library repository on disk and return its path.

    Every argument has a working default, so a test states only the part it
    cares about. Anything in extra goes into installer.yml as it is.
    """

    def build(name="demo", headers=("src/demo.h",), sources=("src/demo.c",), zephyr=None,
              requires=None, defines=None, layout="flat", extra=None, files=None, root=None):
        root = Path(root) if root else tmp_path / name
        root.mkdir(parents=True, exist_ok=True)

        written = {header: f"/**\n * @version 1.2.0\n */\nint {name}_answer(void);\n" for header in headers}
        written.update({source: "int answer(void) { return 42; }\n" for source in sources})
        written.update(files or {})

        for relative, text in written.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

        data = {
            "name": name,
            "description": "A library for the tests",
            "repository": f"https://github.com/someone/{name}",
            "install": {"layout": layout},
            "files": {"headers": list(headers), "sources": list(sources)},
        }

        if defines:
            data["install"]["defines"] = list(defines)

        if requires is not None:
            data["requires"] = requires

        if zephyr is not None:
            data["zephyr"] = zephyr

        data.update(extra or {})
        (root / "installer.yml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

        return root

    return build


@pytest.fixture
def app(tmp_path):
    """A Zephyr application on disk: CMakeLists.txt, prj.conf, and any other files given."""

    def build(prj="CONFIG_GPIO=y\n", cmakelists=CMAKELISTS, files=None, crlf=False, root=None):
        root = Path(root) if root else tmp_path / "app"
        root.mkdir(parents=True, exist_ok=True)
        written = {"CMakeLists.txt": cmakelists, "src/main.c": "int main(void) { return 0; }\n"}

        if prj is not None:
            written["prj.conf"] = prj

        written.update(files or {})

        for relative, text in written.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            data = text.replace("\n", "\r\n") if crlf else text
            path.write_bytes(data.encode("utf-8"))

        return root

    return build


@pytest.fixture
def no_network(monkeypatch):
    """Fail loudly if a test that should stay offline goes online."""

    def refuse(*args, **kwargs):
        raise AssertionError("tried to use the network")

    monkeypatch.setattr(download, "fetch", refuse)


@pytest.fixture
def nobody(monkeypatch):
    """Nobody at the keyboard: every question takes its default."""
    monkeypatch.setattr(cli, "_answer", lambda prompt: None)


@pytest.fixture
def answers(monkeypatch):
    """Answer the questions with these, in order, and keep the questions asked."""
    asked = []

    def give(*replies):
        queue = list(replies)

        def answer(prompt):
            asked.append(prompt)
            return queue.pop(0) if queue else None

        monkeypatch.setattr(cli, "_answer", answer)

        return asked

    return give


def read(path):
    """A file's bytes as text, line endings untouched."""
    return Path(path).read_bytes().decode("utf-8")
