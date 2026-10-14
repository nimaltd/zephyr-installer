"""
Taking a library out of a Zephyr application.

Installed and then uninstalled, the application's CMakeLists.txt and Kconfig
file are back to the byte they were, and the module files are gone.
"""

import pytest
from conftest import read

from zephyr_installer.core import cli


def _install(*args):
    assert cli.main([str(arg) for arg in args]) == 0


def _uninstall(*args):
    return cli.main(["--uninstall"] + [str(arg) for arg in args])


@pytest.mark.parametrize("crlf", [False, True])
@pytest.mark.parametrize("blank", ["", "\n"])
def test_the_application_is_back_as_it_was(library, app, nobody, no_network, crlf, blank, capsys):
    cmakelists = "cmake_minimum_required(VERSION 3.20.0)\n" + blank + "find_package(Zephyr REQUIRED)\n"
    root = app(cmakelists=cmakelists, prj="CONFIG_GPIO=y\n", crlf=crlf)
    before = {name: read(root / name) for name in ("CMakeLists.txt", "prj.conf")}
    lib = library(requires={"kconfig": ["I2C"]}, zephyr={"settings": [
        {"name": "DEMO_SIZE", "type": "int", "default": 8, "prompt": "Size"}]})

    _install(lib, "--project", root)
    assert read(root / "prj.conf") != before["prj.conf"]

    assert _uninstall("demo", "--project", root) == 0

    assert {name: read(root / name) for name in before} == before
    assert not (root / "modules" / "demo").exists()

    out = capsys.readouterr().out
    assert "CMakeLists.txt  Removed demo from CMakeLists.txt." in out
    assert "prj.conf  Removed demo from prj.conf." in out


def test_one_of_two_libraries_comes_out(library, app, nobody, no_network, tmp_path):
    root = app()
    first = library(name="first", headers=("first.h",), sources=("first.c",), root=tmp_path / "src" / "first")
    second = library(name="second", headers=("second.h",), sources=("second.c",), root=tmp_path / "src" / "second")
    _install(second, "--project", root)
    only_second = {name: read(root / name) for name in ("CMakeLists.txt", "prj.conf")}
    _install(first, "--project", root)

    assert _uninstall("first", "--project", root) == 0

    assert {name: read(root / name) for name in only_second} == only_second
    assert (root / "modules" / "second" / "zephyr" / "module.yml").is_file()


def test_the_block_comes_out_of_the_file_it_is_in(library, app, nobody, no_network):
    root = app(files={"boards/x.conf": "CONFIG_SERIAL=y\n"})
    _install(library(), "--project", root, "--conf", "boards/x.conf")

    assert _uninstall("demo", "--project", root) == 0

    assert read(root / "boards" / "x.conf") == "CONFIG_SERIAL=y\n"
    assert read(root / "prj.conf") == "CONFIG_GPIO=y\n"


def test_a_setting_the_user_set_below_the_block_is_named(library, app, nobody, no_network, capsys):
    """Zephyr stops on a symbol it does not know, so the line cannot just be left without a word."""
    root = app()
    _install(library(zephyr={"settings": [{"name": "DEMO_SIZE", "type": "int", "default": 8, "prompt": "Size"}]}),
             "--project", root)

    with open(root / "prj.conf", "ab") as handle:
        handle.write(b"CONFIG_DEMO_SIZE=16\nCONFIG_OTHER=y\n")

    assert _uninstall("demo", "--project", root) == 0

    assert read(root / "prj.conf") == "CONFIG_GPIO=y\n\nCONFIG_DEMO_SIZE=16\nCONFIG_OTHER=y\n"

    out = capsys.readouterr().out
    assert "manual  prj.conf  prj.conf still sets what came with demo" in out
    assert "          CONFIG_DEMO_SIZE=16" in out
    assert "CONFIG_OTHER" not in out.split("still sets")[1]


def test_a_library_with_its_own_module_leaves_nothing_behind(library, app, nobody, no_network):
    lib = library(files={"zephyr/module.yml": "name: demo\n"}, extra={"extras": ["zephyr/module.yml"]},
                  layout="mirror")
    root = app()
    _install(lib, "--project", root)
    own = root / "modules" / "demo" / "zephyr" / "module.yml"
    assert own.read_text(encoding="utf-8") == "name: demo\n"

    assert _uninstall("demo", "--project", root) == 0

    # An extra the library shipped, so the record names it and it goes with
    # the library. What matters is that nothing of the installer's was left.
    assert not (root / "modules" / "demo").exists()


def test_a_half_written_block_is_left_for_the_user(library, app, nobody, no_network, capsys):
    root = app()
    _install(library(), "--project", root)
    path = root / "prj.conf"
    broken = read(path).replace("# <<< zephyr-installer: demo <<<", "")
    path.write_bytes(broken.encode("utf-8"))

    assert _uninstall("demo", "--project", root) == 0

    assert read(path) == broken
    assert "half written zephyr-installer block for demo" in capsys.readouterr().out


def test_the_help_offers_uninstall_and_key(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--help"])

    out = capsys.readouterr().out
    assert "--uninstall NAME" in out
    assert "--key TOKEN" in out
