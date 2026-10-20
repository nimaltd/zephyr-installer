"""
What 2.0.0 brings to a Zephyr application, as gcore needs it.

Files of the application's own made once (VERSION, an overlay in socs/),
sysbuild settings in sysbuild.conf, and groups of CMake lines in the module and
in the application's CMakeLists.txt, each between markers of its own. And
sysbuild.conf is never taken for the application's Kconfig file.
"""

import json
from pathlib import Path

import pytest
from conftest import CMAKELISTS, read

from zephyr_installer import app as appfile
from zephyr_installer.core import cli, manifest
from zephyr_installer.core.manifest import ManifestError

MODERN = {"zephyr_installer": "2.0.0"}

GCORE = {
    "kconfig": "GCORE",
    "sysbuild": ["BOOTLOADER_MCUBOOT", "BOOT_SIGNATURE_TYPE_ECDSA_P256",
                 'BOOT_SIGNATURE_KEY_FILE="${APP_DIR}/sign_key.pem"'],
    "cmake": [
        {"label": "warnings", "lines": ["zephyr_library_compile_options(-Wall -Wextra)"]},
        {"label": "conf", "where": "before-zephyr",
         "lines": ['list(APPEND EXTRA_CONF_FILE "${CMAKE_CURRENT_SOURCE_DIR}/gcore.conf")']},
        {"label": "report", "where": "after-zephyr", "lines": ['message(STATUS "gcore: built for ${BOARD}")']},
    ],
}

ONCE = [
    {"from": "project/VERSION"},
    {"from": "project/CHANGELOG.md"},
    {"from": "boards/nrf54l15.overlay", "to": "socs/nrf54l15_cpuapp.overlay"},
]

FILES = {
    "project/VERSION": "VERSION_MAJOR = 1\nVERSION_MINOR = 0\n",
    "project/CHANGELOG.md": "# Changelog\n",
    "boards/nrf54l15.overlay": "/ { };\n",
}


def _gcore(library, zephyr=None, once=None, root=None, options=None):
    extra = {"once": ONCE if once is None else once}

    if options:
        extra["options"] = options

    return library(name="gcore", headers=("src/gcore.h",), sources=("src/gcore.c",), requires=MODERN,
                   zephyr=GCORE if zephyr is None else zephyr, extra=extra, files=FILES, root=root)


def _install(source, root, *more):
    return cli.main([str(source), "--project", str(root), *more])


def _record(root):
    return json.loads((Path(root) / ".zephyr-installer.json").read_text())["libraries"]


# ----------------------------------------------------------------------------
# A new application, holding only CMakeLists.txt and prj.conf
# ----------------------------------------------------------------------------


def test_everything_lands_and_no_question_is_asked(library, app, answers, no_network):
    asked = answers()
    root = app()

    assert _install(_gcore(library), root, "--dir", "modules/gcore") == 0

    assert (root / "VERSION").read_text() == FILES["project/VERSION"]
    assert (root / "CHANGELOG.md").is_file()
    assert (root / "socs" / "nrf54l15_cpuapp.overlay").is_file()
    assert "CONFIG_GCORE=y" in read(root / "prj.conf")
    assert "SB_CONFIG_BOOTLOADER_MCUBOOT=y" in read(root / "sysbuild.conf")
    assert not any("Kconfig file" in prompt for prompt in asked)


def test_the_sysbuild_block_is_written_as_sysbuild_reads_it(library, app, nobody, no_network):
    root = app()

    _install(_gcore(library), root, "--dir", "modules/gcore")

    assert read(root / "sysbuild.conf") == (
        "# >>> zephyr-installer: gcore >>>\n"
        "# Added by zephyr-installer, and written again on every install, so set\n"
        "# gcore's sysbuild settings below this block rather than in it.\n"
        "SB_CONFIG_BOOTLOADER_MCUBOOT=y\n"
        "SB_CONFIG_BOOT_SIGNATURE_TYPE_ECDSA_P256=y\n"
        'SB_CONFIG_BOOT_SIGNATURE_KEY_FILE="${APP_DIR}/sign_key.pem"\n'
        "# <<< zephyr-installer: gcore <<<\n"
    )


def test_the_cmake_groups_land_each_in_its_place(library, app, nobody, no_network):
    root = app()

    _install(_gcore(library), root, "--dir", "modules/gcore")

    cmake = read(root / "CMakeLists.txt")
    module = read(root / "modules" / "gcore" / "zephyr" / "CMakeLists.txt")
    modules = cmake.index("# >>> zephyr-installer: gcore >>>")
    conf = cmake.index("# >>> zephyr-installer: gcore/conf >>>")
    report = cmake.index("# >>> zephyr-installer: gcore/report >>>")

    assert modules < conf < cmake.index("find_package(Zephyr") < report
    assert cmake.endswith(
        "# >>> zephyr-installer: gcore/report >>>\n"
        "# From gcore's installer.yml, and written again on every install.\n"
        'message(STATUS "gcore: built for ${BOARD}")\n'
        "# <<< zephyr-installer: gcore/report <<<\n"
    )
    assert ("  # >>> zephyr-installer: gcore/warnings >>>\n"
            "  # From gcore's installer.yml, and written again on every install.\n"
            "  zephyr_library_compile_options(-Wall -Wextra)\n"
            "  # <<< zephyr-installer: gcore/warnings <<<\n") in module
    assert "gcore/conf" not in module


def test_installing_again_changes_nothing_and_says_so(library, app, nobody, no_network, capsys):
    root = app()
    source = _gcore(library)
    _install(source, root, "--dir", "modules/gcore")
    before = {name: read(root / name) for name in ("CMakeLists.txt", "prj.conf", "sysbuild.conf")}
    capsys.readouterr()

    assert _install(source, root, "--dir", "modules/gcore") == 0

    assert {name: read(root / name) for name in before} == before
    out = capsys.readouterr().out
    assert "CMakeLists.txt  CMakeLists.txt already has gcore." in out
    assert "sysbuild.conf  sysbuild.conf already has gcore." in out


def test_a_version_and_an_overlay_the_user_edited_survive_an_update(library, app, nobody, no_network):
    root = app()
    source = _gcore(library)
    _install(source, root, "--dir", "modules/gcore")
    (root / "VERSION").write_text("VERSION_MAJOR = 3\n")
    (root / "socs" / "nrf54l15_cpuapp.overlay").write_text("/* mine */\n")

    _install(source, root, "--dir", "modules/gcore")

    assert (root / "VERSION").read_text() == "VERSION_MAJOR = 3\n"
    assert (root / "socs" / "nrf54l15_cpuapp.overlay").read_text() == "/* mine */\n"


def test_uninstall_takes_every_block_out_and_keeps_every_once_file(library, app, nobody, no_network, capsys):
    root = app()
    _install(_gcore(library), root, "--dir", "modules/gcore")
    capsys.readouterr()

    assert cli.main(["--uninstall", "gcore", "--project", str(root)]) == 0

    assert read(root / "CMakeLists.txt") == CMAKELISTS
    assert read(root / "prj.conf") == "CONFIG_GPIO=y\n"
    assert read(root / "sysbuild.conf") == ""
    assert (root / "VERSION").is_file() and (root / "socs" / "nrf54l15_cpuapp.overlay").is_file()
    assert "VERSION  yours, not removed" in capsys.readouterr().out


# ----------------------------------------------------------------------------
# An application with a sysbuild.conf of its own
# ----------------------------------------------------------------------------


def test_the_block_goes_at_the_end_and_a_symbol_the_user_sets_is_commented(library, app, nobody, no_network, capsys):
    mine = "# my settings\nSB_CONFIG_BOOT_SIGNATURE_TYPE_ECDSA_P256=n\n"
    root = app(files={"sysbuild.conf": mine})

    _install(_gcore(library), root, "--dir", "modules/gcore")

    text = read(root / "sysbuild.conf")
    assert text.startswith(mine + "\n# >>> zephyr-installer: gcore >>>")
    assert ("# SB_CONFIG_BOOT_SIGNATURE_TYPE_ECDSA_P256=y  (left out: sysbuild.conf sets "
            "SB_CONFIG_BOOT_SIGNATURE_TYPE_ECDSA_P256=n)") in text
    assert "is left commented: sysbuild.conf sets" in capsys.readouterr().out

    cli.main(["--uninstall", "gcore", "--project", str(root)])

    assert read(root / "sysbuild.conf") == mine


def test_without_sysbuild_settings_sysbuild_conf_is_never_touched(library, app, nobody, no_network):
    root = app()
    zephyr = dict(GCORE)
    del zephyr["sysbuild"]

    _install(_gcore(library, zephyr=zephyr), root, "--dir", "modules/gcore")

    assert not (root / "sysbuild.conf").exists()


def test_a_version_without_sysbuild_settings_takes_the_block_out(library, app, nobody, no_network, tmp_path):
    root = app()
    _install(_gcore(library, root=tmp_path / "v1"), root, "--dir", "modules/gcore")
    zephyr = dict(GCORE)
    del zephyr["sysbuild"]

    _install(_gcore(library, zephyr=zephyr, root=tmp_path / "v2"), root, "--dir", "modules/gcore")

    assert "gcore" not in read(root / "sysbuild.conf")


@pytest.mark.parametrize("given, symbol", [
    ("SB_CONFIG_BOOTLOADER_MCUBOOT", "BOOTLOADER_MCUBOOT"),
    ("MCUBOOT_X=0x10", "MCUBOOT_X"),
])
def test_a_sysbuild_setting_is_written_without_its_prefix(library, given, symbol):
    loaded = manifest.load(_gcore(library, zephyr={"sysbuild": [given]}))

    assert loaded.zephyr.sysbuild[0].symbol == symbol


@pytest.mark.parametrize("sysbuild, says", [
    (["lower"], "capitals"),
    (["X=two words"], "SYMBOL=value"),
    ("BOOTLOADER_MCUBOOT", "a list of settings"),
    (["A", "SB_CONFIG_A"], "more than once"),
])
def test_a_sysbuild_setting_that_cannot_be_written_is_refused(library, sysbuild, says):
    with pytest.raises(ManifestError, match=says):
        manifest.load(_gcore(library, zephyr={"sysbuild": sysbuild}))


# ----------------------------------------------------------------------------
# sysbuild.conf is not the application's Kconfig file
# ----------------------------------------------------------------------------


def test_sysbuild_conf_is_never_offered_as_the_kconfig_file(app):
    root = app(files={"sysbuild.conf": "SB_CONFIG_X=y\n", "debug.conf": ""})

    assert appfile.conf_files(root) == ["prj.conf", "debug.conf"]


def test_a_block_in_sysbuild_is_not_taken_for_the_librarys_kconfig_file(app):
    block = "# >>> zephyr-installer: gcore >>>\nSB_CONFIG_X=y\n# <<< zephyr-installer: gcore <<<\n"
    root = app(files={"sysbuild.conf": block, "sysbuild/mcuboot.conf": block})

    assert appfile.holding(root, "gcore") is None


def test_conf_sysbuild_conf_is_refused(library, app, nobody, no_network, capsys):
    root = app()

    assert _install(_gcore(library), root, "--conf", "sysbuild.conf") == 2

    assert "sysbuild settings go in zephyr.sysbuild" in capsys.readouterr().err
    assert not (root / "modules").exists()


@pytest.mark.parametrize("to", ["CMakeLists.txt", "prj.conf", "sysbuild.conf"])
def test_a_once_file_naming_a_file_this_edits_is_refused(library, app, nobody, no_network, to, capsys):
    root = app()

    assert _install(_gcore(library, once=[{"from": "project/VERSION", "to": to}]), root) == 2

    assert "edits or reads as the project's own" in capsys.readouterr().err


# ----------------------------------------------------------------------------
# Groups of CMake lines
# ----------------------------------------------------------------------------


def _with_groups(library, groups, root=None, options=None):
    return _gcore(library, zephyr={"kconfig": "GCORE", "cmake": groups}, once=[], root=root, options=options)


def test_two_groups_in_one_place_keep_the_manifests_order(library, app, nobody, no_network):
    root = app()
    groups = [{"label": "b", "where": "after-zephyr", "lines": ["b()"]},
              {"label": "a", "where": "after-zephyr", "lines": ["a()"]}]

    _install(_with_groups(library, groups), root, "--dir", "modules/gcore")
    _install(_with_groups(library, groups), root, "--dir", "modules/gcore")

    text = read(root / "CMakeLists.txt")
    assert text.index("gcore/b >>>") < text.index("gcore/a >>>")
    assert text.count("gcore/a >>>") == 1


def test_changing_a_groups_lines_changes_only_its_block(library, app, nobody, no_network, tmp_path):
    root = app()
    one = [{"label": "a", "where": "after-zephyr", "lines": ["a()"]},
           {"label": "b", "where": "before-zephyr", "lines": ["b()"]}]
    two = [{"label": "a", "where": "after-zephyr", "lines": ["a(2)"]},
           {"label": "b", "where": "before-zephyr", "lines": ["b()"]}]
    _install(_with_groups(library, one, root=tmp_path / "v1"), root, "--dir", "modules/gcore")
    before = read(root / "CMakeLists.txt")

    _install(_with_groups(library, two, root=tmp_path / "v2"), root, "--dir", "modules/gcore")

    assert read(root / "CMakeLists.txt") == before.replace("\na()\n", "\na(2)\n")


def test_a_changed_block_is_reported_as_updated(library, app, nobody, no_network, tmp_path, capsys):
    root = app()
    _install(_with_groups(library, [{"label": "a", "where": "after-zephyr", "lines": ["a()"]}],
                          root=tmp_path / "v1"), root, "--dir", "modules/gcore")
    assert "Added gcore to CMakeLists.txt." in capsys.readouterr().out

    _install(_with_groups(library, [{"label": "a", "where": "after-zephyr", "lines": ["a(2)"]}],
                          root=tmp_path / "v2"), root, "--dir", "modules/gcore")

    assert "Updated gcore in CMakeLists.txt." in capsys.readouterr().out


def test_a_changed_block_with_no_label_is_reported_as_updated(library, app, nobody, no_network, tmp_path,
                                                              capsys):
    root = app()
    _install(library(name="plain", requires={"kconfig": ["I2C"]}, root=tmp_path / "v1"), root)
    assert "Added plain to prj.conf." in capsys.readouterr().out

    _install(library(name="plain", requires={"kconfig": ["SPI"]}, root=tmp_path / "v2"), root)

    assert "Updated plain in prj.conf." in capsys.readouterr().out


def test_a_group_taken_out_of_the_manifest_has_only_its_block_removed(library, app, nobody, no_network, tmp_path):
    root = app()
    one = [{"label": "a", "where": "after-zephyr", "lines": ["a()"]},
           {"label": "b", "where": "after-zephyr", "lines": ["b()"]}]
    _install(_with_groups(library, one[:1], root=tmp_path / "v0"), root, "--dir", "modules/gcore")
    only_a = read(root / "CMakeLists.txt")
    _install(_with_groups(library, one, root=tmp_path / "v1"), root, "--dir", "modules/gcore")

    _install(_with_groups(library, one[:1], root=tmp_path / "v2"), root, "--dir", "modules/gcore")

    assert read(root / "CMakeLists.txt") == only_a


def test_a_group_whose_place_changes_is_moved(library, app, nobody, no_network, tmp_path):
    root = app()
    _install(_with_groups(library, [{"label": "a", "where": "after-zephyr", "lines": ["a()"]}],
                          root=tmp_path / "v1"), root, "--dir", "modules/gcore")

    _install(_with_groups(library, [{"label": "a", "where": "before-zephyr", "lines": ["a()"]}],
                          root=tmp_path / "v2"), root, "--dir", "modules/gcore")

    text = read(root / "CMakeLists.txt")
    assert text.index("gcore/a >>>") < text.index("find_package(Zephyr")
    assert text.count("gcore/a >>>") == 1


def test_two_groups_with_one_label_are_refused(library):
    groups = [{"label": "a", "lines": ["a()"]}, {"label": "a", "where": "after-zephyr", "lines": ["b()"]}]

    with pytest.raises(ManifestError, match="two groups labelled a"):
        manifest.load(_with_groups(library, groups))


def test_an_options_groups_come_with_it_and_go_with_it(library, app, nobody, no_network):
    root = app()
    options = {"report": {"description": "Say the board", "zephyr": {"cmake": [
        {"label": "board", "where": "after-zephyr", "lines": ['message(STATUS "${BOARD}")']}]}}}
    source = _with_groups(library, [], options=options)

    _install(source, root, "--dir", "modules/gcore", "--with", "report")
    assert "gcore/board >>>" in read(root / "CMakeLists.txt")

    _install(source, root, "--dir", "modules/gcore", "--without", "report")
    assert "gcore/board" not in read(root / "CMakeLists.txt")


def test_an_options_label_taken_by_the_library_is_refused(library):
    options = {"x": {"description": "x", "zephyr": {"cmake": [{"label": "a", "lines": ["b()"]}]}}}

    with pytest.raises(ManifestError, match="two groups labelled a"):
        manifest.load(_with_groups(library, [{"label": "a", "lines": ["a()"]}], options=options))


def test_the_plain_list_from_before_still_installs_as_it_always_did(library, app, nobody, no_network):
    root = app()
    source = library(name="old", zephyr={"cmake": ["zephyr_library_compile_options(-O2)"]})

    _install(source, root, "--dir", "modules/old")

    module = read(root / "modules" / "old" / "zephyr" / "CMakeLists.txt")
    assert "  # From old's installer.yml.\n  zephyr_library_compile_options(-O2)\n" in module
    assert ">>>" not in module


def test_an_edit_inside_a_block_is_said_and_the_block_written_again(library, app, nobody, no_network, capsys):
    root = app()
    source = _with_groups(library, [{"label": "a", "where": "after-zephyr", "lines": ["a()"]}])
    _install(source, root, "--dir", "modules/gcore")
    path = root / "CMakeLists.txt"
    path.write_bytes(read(path).replace("\na()\n", "\na(mine)\n").encode("utf-8"))
    capsys.readouterr()

    _install(source, root, "--dir", "modules/gcore")

    assert "\na()\n" in read(path)
    assert "Your change inside the gcore/a block is replaced" in capsys.readouterr().out
    assert _record(root)["gcore"]["blocks"]["CMakeLists.txt"]["gcore/a"]


def test_a_project_from_1_x_updates_without_a_change(library, app, nobody, no_network):
    """The same markers, the same text: what 1.1.1 wrote, 2.0.0 leaves as it is."""
    root = app(files={"prj.conf": "CONFIG_GPIO=y\n"})
    source = library(name="demo")
    _install(source, root, "--dir", "modules/demo")
    files = {name: read(root / name) for name in ("CMakeLists.txt", "prj.conf")}
    module = read(root / "modules" / "demo" / "zephyr" / "CMakeLists.txt")

    _install(source, root, "--dir", "modules/demo")

    assert {name: read(root / name) for name in files} == files
    assert read(root / "modules" / "demo" / "zephyr" / "CMakeLists.txt") == module
