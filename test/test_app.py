"""The application's CMakeLists.txt and Kconfig file, and which Kconfig file is used."""

from pathlib import Path

from conftest import CMAKELISTS, read

# Not imported as app, which is the name of the fixture.
from zephyr_installer import app as appfile
from zephyr_installer.core import manifest, target
from zephyr_installer.core.target import ALREADY, CHANGED, MANUAL


def _lib(library, **kwargs):
    return manifest.load(library(**kwargs))


def _backups(root):
    return sorted(p.name for p in Path(root).rglob("*.bak"))


# ----------------------------------------------------------------------------
# CMakeLists.txt
# ----------------------------------------------------------------------------

BLOCK = """# >>> zephyr-installer: demo >>>
# Added by zephyr-installer. Delete this block, and demo's block in
# the Kconfig file, to drop the library from the build.
list(APPEND ZEPHYR_EXTRA_MODULES "${CMAKE_CURRENT_SOURCE_DIR}/modules/demo")
# <<< zephyr-installer: demo <<<"""


def test_the_module_is_added_above_find_package(library, app):
    root = app()
    outcome = app_cmake(root, _lib(library))

    assert outcome.status == CHANGED
    assert outcome.backup is not None
    assert read(root / "CMakeLists.txt") == CMAKELISTS.replace(
        "find_package(", "\n" + BLOCK + "\n\nfind_package(", 1)


def app_cmake(root, lib, folder="modules/demo"):
    return appfile.integrate_cmake(root, lib, Path(root) / folder)


def test_a_second_install_changes_nothing(library, app):
    root = app()
    lib = _lib(library)
    app_cmake(root, lib)
    before = read(root / "CMakeLists.txt")
    backups = _backups(root)

    outcome = app_cmake(root, lib)

    assert outcome.status == ALREADY
    assert read(root / "CMakeLists.txt") == before
    assert _backups(root) == backups


def test_a_library_moved_to_another_folder_keeps_one_block(library, app):
    root = app()
    lib = _lib(library)
    app_cmake(root, lib)

    app_cmake(root, lib, "libs/demo")
    text = read(root / "CMakeLists.txt")

    assert text.count("zephyr-installer: demo >>>") == 1
    assert '"${CMAKE_CURRENT_SOURCE_DIR}/libs/demo"' in text
    assert "modules/demo" not in text


def test_a_block_below_find_package_is_moved_above_it(library, app):
    """Read after find_package(Zephyr), the list is never seen."""
    root = app(cmakelists=CMAKELISTS + "\n" + BLOCK + "\n")

    app_cmake(root, _lib(library))
    text = read(root / "CMakeLists.txt")

    assert text.count("zephyr-installer: demo >>>") == 1
    assert text.index("zephyr-installer: demo") < text.index("find_package(Zephyr")
    assert text.endswith("target_sources(app PRIVATE src/main.c)\n\n")


def test_two_libraries_get_a_block_each(library, app, tmp_path):
    root = app()
    app_cmake(root, _lib(library))
    app_cmake(root, _lib(library, name="osal", headers=("osal.h",), sources=()), "modules/osal")
    text = read(root / "CMakeLists.txt")

    assert text.index("zephyr-installer: demo >>>") < text.index("zephyr-installer: osal >>>")
    assert text.index("zephyr-installer: osal <<<") < text.index("find_package(Zephyr")
    assert "# <<< zephyr-installer: demo <<<\n\n# >>> zephyr-installer: osal >>>" in text


def test_a_half_written_block_is_left_for_the_user(library, app):
    broken = CMAKELISTS.replace("find_package(", "# >>> zephyr-installer: demo >>>\nfind_package(")
    root = app(cmakelists=broken)

    outcome = app_cmake(root, _lib(library))

    assert outcome.status == MANUAL
    assert "half written" in outcome.message
    assert read(root / "CMakeLists.txt") == broken
    assert _backups(root) == []


def test_without_find_package_nothing_is_written(library, app):
    root = app(cmakelists="# find_package(Zephyr) is commented out here\nproject(x)\n", prj="CONFIG_GPIO=y\n")

    outcomes = appfile.integrate(root, _lib(library), root / "modules" / "demo", "prj.conf")

    assert [o.status for o in outcomes] == [MANUAL]
    assert "above find_package(Zephyr)" in outcomes[0].steps[0]
    assert any("ZEPHYR_EXTRA_MODULES" in step for step in outcomes[0].steps)
    assert read(root / "prj.conf") == "CONFIG_GPIO=y\n"
    assert _backups(root) == []


def test_crlf_files_stay_crlf(library, app):
    root = app(crlf=True, prj="CONFIG_GPIO=y\n")

    appfile.integrate(root, _lib(library, requires={"kconfig": ["I2C"]}), root / "modules" / "demo", "prj.conf")

    for name in ("CMakeLists.txt", "prj.conf"):
        text = read(root / name)
        assert "zephyr-installer: demo" in text
        assert text.count("\n") == text.count("\r\n"), name


def test_a_folder_name_cannot_break_out_of_its_argument(library, app):
    root = app()

    app_cmake(root, _lib(library), "my $libs;x/demo")

    assert '"${CMAKE_CURRENT_SOURCE_DIR}/my \\$libs\\;x/demo"' in read(root / "CMakeLists.txt")


def test_a_folder_on_another_drive_is_written_whole(library, app, monkeypatch):
    root = app()
    monkeypatch.setattr(appfile, "relative", lambda path, start: None)

    app_cmake(root, _lib(library))

    expected = '"' + (root / "modules" / "demo").resolve().as_posix() + '"'
    assert f"list(APPEND ZEPHYR_EXTRA_MODULES {expected})" in read(root / "CMakeLists.txt")


# ----------------------------------------------------------------------------
# The Kconfig file
# ----------------------------------------------------------------------------


def test_the_library_is_switched_on_with_what_it_needs(library, app):
    root = app(prj="CONFIG_GPIO=y\n")
    lib = _lib(library, requires={"kconfig": ["I2C", "MAIN_STACK_SIZE=2048"]}, zephyr={"settings": [
        {"name": "DEMO_SIZE", "type": "int", "default": 8, "prompt": "Size"},
    ]})

    outcome = appfile.integrate_conf(root, lib, "prj.conf")

    assert outcome.status == CHANGED
    assert read(root / "prj.conf") == """CONFIG_GPIO=y

# >>> zephyr-installer: demo >>>
# Added by zephyr-installer, and written again on every install, so set
# demo's settings below this block rather than in it.
# Its settings, as they are unless you set them:
#   CONFIG_DEMO_SIZE=8
CONFIG_I2C=y
CONFIG_MAIN_STACK_SIZE=2048
CONFIG_DEMO=y
# <<< zephyr-installer: demo <<<
"""
    assert appfile.integrate_conf(root, lib, "prj.conf").status == ALREADY


def test_what_the_user_set_is_not_set_again(library, app):
    """A later line wins in Kconfig, so the block would quietly undo the user's choice."""
    root = app(crlf=True, prj="CONFIG_I2C=n\n# CONFIG_LOG is not set\nCONFIG_DEMO=n\n")
    lib = _lib(library, requires={"kconfig": ["I2C", "LOG", "GPIO"]})

    appfile.integrate_conf(root, lib, "prj.conf")
    text = read(root / "prj.conf")
    block = text[text.index("# >>>"):]

    assert "CONFIG_GPIO=y" in block
    assert "CONFIG_I2C" not in block
    assert "CONFIG_LOG" not in block
    assert "CONFIG_DEMO" not in block


def test_what_the_user_wrote_around_the_block_is_kept(library, app):
    root = app(prj="CONFIG_GPIO=y\n")
    lib = _lib(library, requires={"kconfig": ["I2C"]})
    appfile.integrate_conf(root, lib, "prj.conf")

    with open(root / "prj.conf", "ab") as handle:
        handle.write(b"CONFIG_DEMO_SIZE=16\n")

    lib = _lib(library, requires={"kconfig": ["SPI"]})
    appfile.integrate_conf(root, lib, "prj.conf")
    text = read(root / "prj.conf")

    assert text.startswith("CONFIG_GPIO=y\n\n# >>>")
    assert text.endswith("# <<< zephyr-installer: demo <<<\nCONFIG_DEMO_SIZE=16\n")
    assert "CONFIG_SPI=y" in text
    assert "CONFIG_I2C" not in text


def test_a_missing_kconfig_file_is_created(library, app):
    root = app(prj=None)

    outcome = appfile.integrate_conf(root, _lib(library), "boards/nrf52840dk_nrf52840.conf")

    assert outcome.status == CHANGED
    assert outcome.backup is None
    assert read(root / "boards" / "nrf52840dk_nrf52840.conf").startswith("# >>> zephyr-installer: demo >>>\n")


def test_a_half_written_block_in_the_kconfig_file_is_left_for_the_user(library, app):
    root = app(prj="# >>> zephyr-installer: demo >>>\nCONFIG_GPIO=y\n")

    outcome = appfile.integrate_conf(root, _lib(library), "prj.conf")

    assert outcome.status == MANUAL
    assert read(root / "prj.conf") == "# >>> zephyr-installer: demo >>>\nCONFIG_GPIO=y\n"


def test_a_symbol_set_in_prj_conf_counts_for_a_board_file(library, app):
    """Zephyr reads a board's own file with prj.conf, so a value in either is the user's."""
    root = app(prj="CONFIG_I2C=y\n", files={"boards/x.conf": "CONFIG_SPI=n\n"})

    appfile.integrate_conf(root, _lib(library, requires={"kconfig": ["I2C", "SPI", "GPIO"]}), "boards/x.conf")
    block = read(root / "boards" / "x.conf").split("# >>>")[1]

    assert "CONFIG_GPIO=y" in block
    assert "CONFIG_I2C" not in block
    assert "CONFIG_SPI" not in block


# ----------------------------------------------------------------------------
# Which Kconfig file
# ----------------------------------------------------------------------------


def test_the_kconfig_files_offered_start_with_prj_conf(app):
    root = app(files={"boards/b.conf": "", "boards/a.conf": "", "debug.conf": "", "boards/x.txt": ""})

    assert appfile.conf_files(root) == ["prj.conf", "debug.conf", "boards/a.conf", "boards/b.conf"]


def test_prj_conf_when_there_is_nothing_to_choose(library, app, fresh_run):
    root = app()
    fresh_run.ask = lambda prompt: "never asked"

    assert fresh_run.conf_for(_lib(library), root) == "prj.conf"


def test_the_choice_is_asked_once_for_every_library_of_the_run(library, app, fresh_run):
    root = app(files={"boards/x.conf": ""})
    asked = []
    fresh_run.ask = lambda prompt: asked.append(prompt) or "boards/x.conf"

    assert fresh_run.conf_for(_lib(library), root) == "boards/x.conf"
    assert fresh_run.conf_for(_lib(library, name="osal", headers=("o.h",), sources=()), root) == "boards/x.conf"
    assert len(asked) == 1
    assert "[prj.conf]" in asked[0]


def test_nobody_to_ask_means_prj_conf(library, app, fresh_run):
    root = app(files={"boards/x.conf": ""})
    fresh_run.ask = lambda prompt: None

    assert fresh_run.conf_for(_lib(library), root) == "prj.conf"


def test_conf_given_on_the_command_line_is_used_without_a_question(library, app, fresh_run):
    root = app(files={"boards/x.conf": ""})
    fresh_run.conf_given = "debug.conf"
    fresh_run.ask = lambda prompt: "asked anyway"

    assert fresh_run.conf_for(_lib(library), root) == "debug.conf"


def test_a_library_already_in_a_file_stays_there(library, app, fresh_run):
    root = app(files={"conf/release.conf": "# >>> zephyr-installer: demo >>>\n# <<< zephyr-installer: demo <<<\n"})
    fresh_run.conf_given = "prj.conf"
    fresh_run.ask = lambda prompt: "asked anyway"

    assert fresh_run.conf_for(_lib(library), root) == "conf/release.conf"


def test_a_block_in_the_build_folder_does_not_count(app):
    root = app(files={"build/zephyr.conf": "# >>> zephyr-installer: demo >>>\n# <<< zephyr-installer: demo <<<\n"})

    assert appfile.holding(root, "demo") is None


def test_the_installer_is_this_target():
    assert target.current.name == "zephyr-installer"
