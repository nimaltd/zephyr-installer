"""The parts of installer.yml only zephyr-installer reads: zephyr, and requires.kconfig."""

import pytest

from zephyr_installer.core import manifest
from zephyr_installer.core.manifest import ManifestError


def _setting(**fields):
    entry = {"name": "DEMO_SIZE", "type": "int", "default": 8, "prompt": "Size"}
    entry.update(fields)

    return entry


def _load(library, **kwargs):
    return manifest.load(library(**kwargs))


# ----------------------------------------------------------------------------
# The library's own symbol
# ----------------------------------------------------------------------------


def test_the_symbol_is_the_name_in_capitals(library):
    assert _load(library).zephyr.symbol == "DEMO"
    assert _load(library, name="one-wire", headers=("src/ow.h",), sources=()).zephyr.symbol == "ONE_WIRE"


def test_the_symbol_can_be_given(library):
    assert _load(library, zephyr={"kconfig": "NIMALTD_DEMO"}).zephyr.symbol == "NIMALTD_DEMO"
    assert _load(library, zephyr={"kconfig": "CONFIG_NIMALTD_DEMO"}).zephyr.symbol == "NIMALTD_DEMO"


def test_a_symbol_in_small_letters_is_refused(library):
    with pytest.raises(ManifestError, match="zephyr.kconfig"):
        _load(library, zephyr={"kconfig": "demo"})


def test_a_zephyr_section_that_is_not_a_mapping_is_refused(library):
    with pytest.raises(ManifestError, match="zephyr should hold"):
        _load(library, zephyr=["DEMO"])


# ----------------------------------------------------------------------------
# Settings
# ----------------------------------------------------------------------------


def test_each_type_of_setting_is_read_as_kconfig_writes_it(library):
    settings = _load(library, zephyr={"settings": [
        _setting(name="DEMO_SIZE", type="int", default=8, range=[1, 64]),
        _setting(name="DEMO_BASE", type="hex", default=4096, range=["0x1000", 65535]),
        _setting(name="DEMO_FAST", type="bool", default=True),
        _setting(name="DEMO_SLOW", type="bool", default="n"),
        _setting(name="DEMO_NAME", type="string", default='say "hi" \\ there'),
    ]}).zephyr.settings

    assert [s.line for s in settings] == [
        "CONFIG_DEMO_SIZE=8",
        "CONFIG_DEMO_BASE=0x1000",
        "CONFIG_DEMO_FAST=y",
        "CONFIG_DEMO_SLOW=n",
        'CONFIG_DEMO_NAME="say \\"hi\\" \\\\ there"',
    ]
    assert settings[0].range == (1, 64)
    assert settings[1].range == (0x1000, 0xFFFF)


def test_a_setting_written_with_config_in_front_loses_it(library):
    setting = _load(library, zephyr={"settings": [_setting(name="CONFIG_DEMO_SIZE")]}).zephyr.settings[0]

    assert setting.name == "DEMO_SIZE"


def test_the_prompt_is_one_line_with_its_quotes_escaped(library):
    setting = _load(library, zephyr={"settings": [_setting(prompt='Bytes, "at most"\nper call')]}).zephyr.settings[0]

    assert setting.prompt == 'Bytes, \\"at most\\" per call'


@pytest.mark.parametrize("fields, words", [
    ({"type": "float"}, "type"),
    ({"type": None}, "type"),
    ({"default": None}, "no default"),
    ({"default": 99, "range": [1, 64]}, "outside its range"),
    ({"default": "eight"}, "not a number"),
    ({"default": True}, "not a number"),
    ({"range": [64, 1]}, "starts above"),
    ({"range": [1]}, "smallest, largest"),
    ({"type": "string", "default": "x", "range": [1, 2]}, "only an int or a hex"),
    ({"type": "bool", "default": "maybe"}, "true or false"),
    ({"type": "string", "default": "two\nlines"}, "one line"),
    ({"name": "demo_size"}, "capitals"),
    ({"name": "DEMO"}, "library's own symbol"),
])
def test_a_setting_that_kconfig_could_not_take_is_refused(library, fields, words):
    with pytest.raises(ManifestError, match=words):
        _load(library, zephyr={"settings": [_setting(**fields)]})


def test_a_setting_given_twice_is_refused(library):
    with pytest.raises(ManifestError, match="more than once"):
        _load(library, zephyr={"settings": [_setting(), _setting()]})


def test_settings_have_to_be_a_list_of_mappings(library):
    with pytest.raises(ManifestError, match="is a list"):
        _load(library, zephyr={"settings": {"DEMO_SIZE": 8}})

    with pytest.raises(ManifestError, match="one entry per setting"):
        _load(library, zephyr={"settings": ["DEMO_SIZE"]})


def test_a_setting_without_a_prompt_or_the_library_prefix_is_warned_about(library):
    loaded = _load(library, zephyr={"settings": [_setting(name="SIZE", prompt=None)]})

    assert any("does not start with DEMO_" in warning for warning in loaded.warnings)
    assert any("has no prompt" in warning for warning in loaded.warnings)
    assert loaded.zephyr.settings[0].prompt == "SIZE"


def test_a_good_setting_brings_no_warning(library):
    assert _load(library, zephyr={"settings": [_setting()]}).warnings == []


# ----------------------------------------------------------------------------
# requires
# ----------------------------------------------------------------------------


def test_required_symbols_are_set_to_y_unless_a_value_is_given(library):
    loaded = _load(library, requires={"kconfig": ["I2C", "CONFIG_GPIO", "MAIN_STACK_SIZE=2048",
                                                  "HEAP=0x400", 'NAME="x"', "LOG=n"]})

    assert [r.line for r in loaded.requires.kconfig] == [
        "CONFIG_I2C=y", "CONFIG_GPIO=y", "CONFIG_MAIN_STACK_SIZE=2048",
        "CONFIG_HEAP=0x400", 'CONFIG_NAME="x"', "CONFIG_LOG=n",
    ]


@pytest.mark.parametrize("entry", ["i2c", "I2C=yes please", "I2C=1 # on", 'NAME="a"b"'])
def test_a_required_symbol_written_wrong_is_refused(library, entry):
    with pytest.raises(ManifestError, match="requires.kconfig"):
        _load(library, requires={"kconfig": [entry]})


def test_required_symbols_have_to_be_a_list(library):
    with pytest.raises(ManifestError, match="list of symbols"):
        _load(library, requires={"kconfig": "I2C"})


def test_peripherals_are_read_for_the_user(library):
    loaded = _load(library, requires={"peripherals": [{"type": "i2c", "count": 2, "note": "400 kHz"}, "spi"]})

    assert [p.describe() for p in loaded.requires.peripherals] == ["I2C x2, 400 kHz", "SPI"]
    assert not loaded.requires.is_empty()


def test_a_library_for_a_newer_zephyr_installer_is_refused(library):
    with pytest.raises(ManifestError) as raised:
        _load(library, requires={"zephyr_installer": "9.0.0"})

    assert "needs zephyr-installer 9.0.0" in str(raised.value)
    assert "pip install --upgrade zephyr-installer" in str(raised.value)


def test_what_stm32_installer_needs_is_not_this_ones_business(library):
    loaded = _load(library, requires={"installer": "99.0.0", "hal_modules": ["spi"], "rtos": "freertos"})

    assert loaded.requires.is_empty()
