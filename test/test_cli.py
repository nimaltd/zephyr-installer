"""The whole command, from the command line to the files it leaves, and what it checks first."""

import json

import pytest
from conftest import read

from zephyr_installer import __version__
from zephyr_installer.core import cli, manifest, target
from zephyr_installer.core.target import INFO, OK, WARN


def _install(*args):
    return cli.main([str(arg) for arg in args])


# ----------------------------------------------------------------------------
# The command
# ----------------------------------------------------------------------------


def test_the_version_is_the_packages(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--version"])

    assert capsys.readouterr().out.strip() == f"zephyr-installer {__version__}"


def test_the_help_offers_conf_and_no_ide(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--help"])

    out = capsys.readouterr().out
    assert "--conf FILE" in out
    assert "--ide" not in out
    assert "Zephyr application" in out


def test_nothing_to_install_says_how(capsys):
    assert cli.main([]) == 2
    assert "zephyr-installer owner/example" in capsys.readouterr().err


# ----------------------------------------------------------------------------
# A whole install
# ----------------------------------------------------------------------------


def test_a_library_goes_into_modules_and_is_switched_on(library, app, nobody, no_network, capsys):
    lib = library(requires={"kconfig": ["I2C"]})
    root = app()

    assert _install(lib, "--project", root) == 0

    assert (root / "modules" / "demo" / "demo.h").is_file()
    assert (root / "modules" / "demo" / "zephyr" / "module.yml").is_file()
    assert '"${CMAKE_CURRENT_SOURCE_DIR}/modules/demo"' in read(root / "CMakeLists.txt")
    assert "CONFIG_I2C=y\nCONFIG_DEMO=y\n" in read(root / "prj.conf")

    record = json.loads(read(root / ".zephyr-installer.json"))
    assert record["libraries"]["demo"]["folder"] == "modules/demo"

    out = capsys.readouterr().out
    assert "CONFIG_I2C=y goes into prj.conf" in out
    assert 'Done. #include "demo.h"' in out


def test_conf_puts_the_symbols_where_it_says(library, app, nobody, no_network):
    root = app(files={"boards/x.conf": "CONFIG_SERIAL=y\n"})

    assert _install(library(), "--project", root, "--conf", "boards/x.conf") == 0

    assert "CONFIG_DEMO=y" in read(root / "boards" / "x.conf")
    assert read(root / "prj.conf") == "CONFIG_GPIO=y\n"


def test_the_question_picks_the_file(library, app, answers, no_network):
    root = app(files={"boards/x.conf": ""})
    # Asked with the requirements, so before the folder.
    asked = answers("boards/x.conf", "libs/demo")

    assert _install(library(), "--project", root) == 0

    assert "CONFIG_DEMO=y" in read(root / "boards" / "x.conf")
    assert (root / "libs" / "demo" / "demo.h").is_file()
    assert "Kconfig file for the libraries [prj.conf]" in asked[0]
    assert "Folder to install demo into [modules/demo]" in asked[1]


def test_a_library_and_the_one_it_needs_go_in_together(library, app, nobody, no_network):
    osal = library(name="osal", headers=("osal.h",), sources=())
    ee24 = library(name="ee24", headers=("ee24.h",), sources=("ee24.c",),
                   requires={"libraries": ["osal"], "kconfig": ["I2C"]})
    root = app()

    assert _install(ee24, osal, "--project", root) == 0

    cmake = read(root / "CMakeLists.txt")
    prj = read(root / "prj.conf")

    assert cmake.index("zephyr-installer: osal >>>") < cmake.index("zephyr-installer: ee24 >>>")
    assert "CONFIG_OSAL=y" in prj
    assert "CONFIG_EE24=y" in prj
    assert prj.count("CONFIG_I2C=y") == 1
    assert "zephyr_library" not in read(root / "modules" / "osal" / "zephyr" / "CMakeLists.txt")


def test_an_update_writes_nothing_new(library, app, nobody, no_network, capsys):
    lib = library()
    root = app()
    _install(lib, "--project", root)
    before = {name: read(root / name) for name in ("CMakeLists.txt", "prj.conf")}
    capsys.readouterr()

    target.current.conf_of = {}
    assert _install(lib, "--project", root) == 0

    assert {name: read(root / name) for name in before} == before
    out = capsys.readouterr().out
    assert "already has demo" in out
    assert "is up to date" in out


def test_outside_a_zephyr_application_the_lines_to_add_are_shown(library, app, nobody, no_network, capsys):
    root = app(cmakelists="project(plain)\n", prj=None)

    assert _install(library(), "--project", root) == 0

    out = capsys.readouterr().out
    assert "No CMakeLists.txt with find_package(Zephyr) here" in out
    assert "list(APPEND ZEPHYR_EXTRA_MODULES" in out
    assert not (root / "prj.conf").exists()


# ----------------------------------------------------------------------------
# What is checked first
# ----------------------------------------------------------------------------


def _check(library, root, **kwargs):
    return [(f.level, f.message) for f in target.current.check(manifest.load(library(**kwargs)), root)]


def test_each_required_symbol_is_reported_as_it_stands(library, app):
    root = app(crlf=True, prj="CONFIG_GPIO=y\n# CONFIG_LOG is not set\n")

    found = _check(library, root, requires={"kconfig": ["GPIO", "LOG", "SPI"]})

    assert found == [
        (OK, "CONFIG_GPIO=y is in prj.conf"),
        (WARN, "prj.conf sets CONFIG_LOG=n, and demo needs y"),
        (INFO, "CONFIG_SPI=y goes into prj.conf"),
    ]


def test_a_symbol_the_block_already_sets_is_reported_as_there(library, app):
    root = app(prj="# >>> zephyr-installer: demo >>>\nCONFIG_SPI=y\n# <<< zephyr-installer: demo <<<\n")

    assert _check(library, root, requires={"kconfig": ["SPI"]}) == [(OK, "CONFIG_SPI=y is in prj.conf")]


def test_hardware_is_pointed_at_the_devicetree(library, app):
    found = target.current.check(manifest.load(library(requires={"peripherals": [{"type": "i2c"}]})), app())

    assert found[0].level == INFO
    assert found[0].message == "Needs I2C"
    assert "devicetree" in found[0].hint


def test_outside_a_zephyr_application_only_that_is_said(library, app):
    root = app(cmakelists="project(plain)\n")

    found = _check(library, root, requires={"kconfig": ["SPI"]})

    assert found == [(WARN, "No CMakeLists.txt with find_package(Zephyr) here")]
