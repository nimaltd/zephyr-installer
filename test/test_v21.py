"""
What 2.1.0 brings to a Zephyr application: every path naming a place in the
project starts at the application's folder, and {library} names the folder the
library was installed in, wherever --dir put it. In a group of CMake lines it
is that folder as CMake reads it.

And zephyr.defaults: the library's settings of other symbols, listed as
requires.kconfig is, which become configdefaults in its Kconfig. They hold
while the library is on, the application's prj.conf holds only its switch,
and a line there that sets one of them wins.
"""

from pathlib import Path

import pytest
from conftest import read

from zephyr_installer.core import cli, manifest
from zephyr_installer.core.manifest import ManifestError

ROOTED = {"zephyr_installer": "2.1.0"}

OVERLAY = 'list(APPEND EXTRA_DTC_OVERLAY_FILE "{library}/dts/gcore.overlay")'

KEYGEN = (
    "from pathlib import Path\n"
    "Path('sign_key.pem').write_text('key')\n"
)


def _gcore(library, cmake, requires=ROOTED, extra=None):
    zephyr = {"kconfig": "GCORE", "cmake": cmake}
    files = {"dts/gcore.overlay": "/ { };\n", "tools/keygen.py": KEYGEN, "tools/keygen.md": "# keygen\n"}

    return library(name="gcore", headers=("src/gcore.h",), sources=("src/gcore.c",), requires=requires,
                   zephyr=zephyr, extra=dict({"once": []}, **(extra or {})), files=files)


def _install(source, root, *more):
    return cli.main([str(source), "--project", str(root), *more])


def test_library_in_the_applications_lines_is_where_dir_put_it(library, app, nobody, no_network):
    root = app()
    lib = _gcore(library, [{"label": "dts", "where": "before-zephyr", "lines": [OVERLAY]}])

    assert _install(lib, root, "--dir", "libs/gcore") == 0

    assert ('list(APPEND EXTRA_DTC_OVERLAY_FILE "${CMAKE_CURRENT_SOURCE_DIR}/libs/gcore/dts/gcore.overlay")'
            in read(root / "CMakeLists.txt"))


def test_library_in_the_modules_lines_is_the_modules_folder(library, app, nobody, no_network):
    root = app()
    lib = _gcore(library, [{"label": "dts", "lines": ['message(STATUS "{library}")']}])

    assert _install(lib, root, "--dir", "modules/gcore") == 0

    module = read(root / "modules" / "gcore" / "zephyr" / "CMakeLists.txt")
    assert 'message(STATUS "${ZEPHYR_CURRENT_MODULE_DIR}")' in module


def test_before_2_1_0_library_is_left_as_it_was_written(library, app, nobody, no_network):
    root = app()
    lib = _gcore(library, [{"label": "dts", "where": "before-zephyr", "lines": [OVERLAY]}],
                 requires={"zephyr_installer": "2.0.0"})

    assert _install(lib, root, "--dir", "modules/gcore") == 0

    assert OVERLAY in read(root / "CMakeLists.txt")


def test_tools_land_beside_cmakelists_and_run_from_there(library, app, nobody, no_network, capsys):
    root = app()
    extra = {
        "extras": [{"root": "tools"}],
        "run": [{"label": "signing-key", "script": "tools/keygen.py", "unless": "sign_key.pem"}],
    }
    lib = _gcore(library, [], extra=extra)

    assert _install(lib, root, "--dir", "modules/gcore", "--run", "signing-key") == 0

    assert (root / "tools" / "keygen.py").is_file()
    assert (root / "tools" / "keygen.md").is_file()
    assert not (root / "modules" / "gcore" / "tools").exists()
    assert (root / "sign_key.pem").read_text() == "key"
    assert "python tools/keygen.py" in capsys.readouterr().out

    # An uninstall takes the tools out, and leaves the key it made.
    assert cli.main(["--uninstall", "gcore", "--project", str(root)]) == 0
    assert not (root / "tools").exists()
    assert Path(root / "sign_key.pem").is_file()


# ----------------------------------------------------------------------------
# zephyr.defaults
# ----------------------------------------------------------------------------

DEFAULTS = ["BT", "CONFIG_BT_PERIPHERAL", "BT_L2CAP_TX_MTU=498", 'BT_DEVICE_NAME="gcore"', "BT_CTLR_LE_PING=n"]


def _with_defaults(library, defaults=DEFAULTS, requires=ROOTED, kconfig=None):
    zephyr = {"kconfig": "GCORE", "defaults": defaults}
    wanted = dict(requires, kconfig=kconfig) if kconfig else requires

    return library(name="gcore", headers=("src/gcore.h",), sources=("src/gcore.c",), requires=wanted,
                   zephyr=zephyr, extra={"once": []})


def test_defaults_land_in_the_kconfig_and_prj_conf_holds_only_the_switch(library, app, nobody,
                                                                          no_network, capsys):
    root = app(prj="")

    assert _install(_with_defaults(library), root, "--dir", "modules/gcore") == 0

    kconfig = read(root / "modules" / "gcore" / "zephyr" / "Kconfig")
    assert ("if GCORE\n"
            "\n"
            "configdefault BT\n"
            "\tdefault y\n"
            "\n"
            "configdefault BT_PERIPHERAL\n"
            "\tdefault y\n"
            "\n"
            "configdefault BT_L2CAP_TX_MTU\n"
            "\tdefault 498\n"
            "\n"
            "configdefault BT_DEVICE_NAME\n"
            '\tdefault "gcore"\n'
            "\n"
            "configdefault BT_CTLR_LE_PING\n"
            "\tdefault n\n"
            "\n"
            "endif # GCORE\n") in kconfig

    prj = read(root / "prj.conf")
    assert "CONFIG_GCORE=y" in prj
    assert "CONFIG_BT" not in prj
    assert "CONFIG_BT=y by default, while CONFIG_GCORE is on" in capsys.readouterr().out


def test_a_line_of_the_applications_own_is_said_to_win(library, app, nobody, no_network, capsys):
    root = app(prj="CONFIG_BT_L2CAP_TX_MTU=247\n")

    assert _install(_with_defaults(library), root, "--dir", "modules/gcore") == 0

    out = capsys.readouterr().out
    assert "sets CONFIG_BT_L2CAP_TX_MTU=247, in place of gcore's default 498" in out
    assert "CONFIG_BT_L2CAP_TX_MTU=247" in read(root / "prj.conf")


def test_an_update_writes_the_new_defaults(library, app, nobody, no_network):
    root = app()
    _install(_with_defaults(library), root, "--dir", "modules/gcore")

    _install(_with_defaults(library, defaults=["BT"]), root, "--dir", "modules/gcore")

    kconfig = read(root / "modules" / "gcore" / "zephyr" / "Kconfig")
    assert "configdefault BT\n" in kconfig
    assert "BT_L2CAP_TX_MTU" not in kconfig


@pytest.mark.parametrize("defaults, says", [
    (["bt"], "Write a Kconfig symbol"),
    (["BT=yes"], "Give a symbol, which is set to y"),
    (['BT_DEVICE_NAME="a \\" b"'], "Give a symbol, which is set to y"),
    (["BT", "BT=n"], "more than once"),
    (["GCORE"], "the library's own switch"),
    ("BT", "is a list"),
])
def test_defaults_that_cannot_be_written_are_refused(library, defaults, says):
    with pytest.raises(ManifestError, match=says):
        manifest.load(_with_defaults(library, defaults=defaults))


def test_a_symbol_in_both_requires_kconfig_and_defaults_is_refused(library):
    with pytest.raises(ManifestError, match="in both requires.kconfig and zephyr.defaults"):
        manifest.load(_with_defaults(library, kconfig=["BT"]))


def test_a_manifest_from_before_cannot_have_them(library):
    with pytest.raises(ManifestError, match="new in 2.1.0"):
        manifest.load(_with_defaults(library, requires={"zephyr_installer": "2.0.0"}))



# ----------------------------------------------------------------------------
# zephyr.cmake by the places the lines go
# ----------------------------------------------------------------------------

PLACED = {
    "before-zephyr": ['list(APPEND EXTRA_DTC_OVERLAY_FILE "${CMAKE_CURRENT_SOURCE_DIR}/dts/gcore.overlay")'],
    "module": ["zephyr_library_compile_options(-Wall)"],
}


def test_each_place_gets_its_block(library, app, nobody, no_network):
    root = app()

    assert _install(_gcore(library, PLACED), root, "--dir", "modules/gcore") == 0

    cmake = read(root / "CMakeLists.txt")
    assert ("# >>> zephyr-installer: gcore/before-zephyr >>>\n"
            "# From gcore's installer.yml, and written again on every install.\n"
            'list(APPEND EXTRA_DTC_OVERLAY_FILE "${CMAKE_CURRENT_SOURCE_DIR}/dts/gcore.overlay")\n'
            "# <<< zephyr-installer: gcore/before-zephyr <<<\n") in cmake
    assert cmake.index("gcore/before-zephyr >>>") < cmake.index("find_package(Zephyr")
    assert "zephyr_library_compile_options(-Wall)" in read(root / "modules" / "gcore" / "zephyr" / "CMakeLists.txt")


def test_a_labelled_group_from_before_gives_way_to_its_place(library, app, nobody, no_network):
    root = app()
    labelled = [{"label": "boot-mode", "where": "before-zephyr", "lines": PLACED["before-zephyr"]}]
    _install(_gcore(library, labelled), root, "--dir", "modules/gcore")
    assert "gcore/boot-mode" in read(root / "CMakeLists.txt")

    _install(_gcore(library, {"before-zephyr": PLACED["before-zephyr"]}), root, "--dir", "modules/gcore")

    cmake = read(root / "CMakeLists.txt")
    assert "gcore/boot-mode" not in cmake
    assert cmake.count("EXTRA_DTC_OVERLAY_FILE") == 1
    assert "gcore/before-zephyr" in cmake


def test_an_options_places_are_named_after_it(library):
    options = {"extra": {"description": "More", "zephyr": {"cmake": {"module": ["more()"]}}}}
    loaded = manifest.load(_gcore(library, {"module": ["a()"]}, extra={"options": options}))

    assert [g.label for g in loaded.options["extra"].zephyr_cmake] == ["extra-module"]
