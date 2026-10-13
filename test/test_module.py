"""The library as a Zephyr module: zephyr/module.yml, CMakeLists.txt and Kconfig."""

import os

from zephyr_installer import module
from zephyr_installer.core import manifest
from zephyr_installer.core.target import ALREADY, CHANGED


def _lib(library, **kwargs):
    return manifest.load(library(**kwargs))


def test_the_module_is_named_apart_from_zephyrs_own(library):
    """A module called littlefs would quietly take the place of Zephyr's littlefs."""
    lib = _lib(library, name="littlefs", headers=("lfs.h",), sources=("lfs.c",))

    assert module.module_name(lib) == "littlefs_lib"
    assert "name: littlefs_lib\n" in module.module_yml(lib)
    assert "  cmake: zephyr\n  kconfig: zephyr/Kconfig\n" in module.module_yml(lib)


def test_the_cmakelists_builds_the_files_only_when_the_symbol_is_set(library):
    text = module.cmakelists(_lib(library, defines=["DEMO_DEFINED=1"]))
    body = text[text.index("if(CONFIG_DEMO)"):]

    assert body == """if(CONFIG_DEMO)
  zephyr_include_directories(
    "${ZEPHYR_CURRENT_MODULE_DIR}"
  )

  zephyr_library_named(demo_lib)
  zephyr_library_sources(
    "${ZEPHYR_CURRENT_MODULE_DIR}/demo.c"
  )

  zephyr_compile_definitions(
    DEMO_DEFINED=1
  )
endif()
"""


def test_a_mirror_layout_keeps_its_folders(library):
    text = module.cmakelists(_lib(library, layout="mirror"))

    assert '"${ZEPHYR_CURRENT_MODULE_DIR}/src"' in text
    assert '"${ZEPHYR_CURRENT_MODULE_DIR}/src/demo.c"' in text


def test_a_library_of_headers_only_has_no_library_to_build(library):
    text = module.cmakelists(_lib(library, sources=()))

    assert "zephyr_include_directories(" in text
    assert "zephyr_library" not in text


def test_a_file_name_cannot_break_out_of_its_argument(library):
    # Windows takes no quote in a file name, so the quote is checked on its own.
    assert module.cmake_quote('a "b" \\c') == '"a \\"b\\" \\\\c"'

    text = module.cmakelists(_lib(library, sources=("my $x;y.c",)))

    assert '"${ZEPHYR_CURRENT_MODULE_DIR}/my \\$x\\;y.c"' in text


def test_the_kconfig_switch_has_the_description_as_its_prompt(library):
    text = module.kconfig(_lib(library))

    assert "config DEMO\n" in text
    assert '\tbool "demo: A library for the tests"\n' in text
    assert "\thelp\n\t  A library for the tests\n\t  https://github.com/someone/demo\n" in text
    assert "menuconfig" not in text
    assert "if DEMO" not in text


def test_settings_sit_under_the_switch(library):
    text = module.kconfig(_lib(library, zephyr={"settings": [
        {"name": "DEMO_SIZE", "type": "int", "default": 8, "range": [1, 64], "prompt": "Size",
         "help": "Bytes in one piece.\n\nSmaller is slower."},
        {"name": "DEMO_BASE", "type": "hex", "default": "0x10", "range": [0, 255], "prompt": "Base"},
        {"name": "DEMO_NAME", "type": "string", "default": "x", "prompt": 'A "name"'},
    ]}))

    assert text.startswith(module.MARK)
    assert "menuconfig DEMO\n" in text
    assert text[text.index("if DEMO"):] == """if DEMO

config DEMO_SIZE
\tint "Size"
\tdefault 8
\trange 1 64
\thelp
\t  Bytes in one piece.

\t  Smaller is slower.

config DEMO_BASE
\thex "Base"
\tdefault 0x10
\trange 0x0 0xff

config DEMO_NAME
\tstring "A \\"name\\""
\tdefault "x"

endif # DEMO
"""


def test_the_files_are_written_and_then_left_alone(library, tmp_path):
    lib = _lib(library)
    folder = tmp_path / "modules" / "demo"

    first = module.write(lib, folder)
    assert first.status == CHANGED
    assert "zephyr/module.yml, zephyr/CMakeLists.txt, zephyr/Kconfig" in first.message

    kconfig = folder / "zephyr" / "Kconfig"
    os.utime(kconfig, (1000000000, 1000000000))

    again = module.write(lib, folder)
    assert again.status == ALREADY
    assert kconfig.stat().st_mtime == 1000000000


def test_a_file_changed_by_hand_is_written_again(library, tmp_path):
    lib = _lib(library)
    folder = tmp_path / "modules" / "demo"
    module.write(lib, folder)
    (folder / "zephyr" / "CMakeLists.txt").write_text("# mine\n", encoding="utf-8")

    outcome = module.write(lib, folder)

    assert outcome.status == CHANGED
    assert outcome.message.endswith("zephyr/CMakeLists.txt.")
    assert (folder / "zephyr" / "CMakeLists.txt").read_text(encoding="utf-8") == module.cmakelists(lib)


def test_a_library_with_its_own_module_is_left_alone(library, tmp_path):
    folder = tmp_path / "modules" / "demo"
    (folder / "zephyr").mkdir(parents=True)
    (folder / "zephyr" / "module.yml").write_text("name: demo\n", encoding="utf-8")

    outcome = module.write(_lib(library), folder)

    assert outcome.status == ALREADY
    assert "its own zephyr/module.yml" in outcome.message
    assert sorted(p.name for p in (folder / "zephyr").iterdir()) == ["module.yml"]
