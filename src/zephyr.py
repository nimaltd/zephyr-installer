"""
What zephyr-installer adds to the shared core: what a Zephyr application is.

The core does everything a library needs whatever it is installed into. This
says the rest for Zephyr: the part of installer.yml only Zephyr reads, the
checks against the application's prj.conf, and the integration, which makes
the library a Zephyr module of the application (module.py) and adds it to the
application's CMakeLists.txt and prj.conf (app.py).
"""

import re
from pathlib import Path

from . import app, module
from .core import console
from .core.manifest import ManifestError
from .core.target import CHANGED, INFO, MANUAL, OK, WARN, Finding, Outcome, Target

# A Kconfig symbol as Zephyr writes them, without CONFIG_ in front.
SYMBOL = re.compile(r"^[A-Z0-9_]+$")

# A value a required symbol may be given in prj.conf: y or n, a number, a hex
# number, or a string in quotes. Written into prj.conf as it stands, so nothing
# else gets through.
VALUE = re.compile(r'^(?:y|n|-?[0-9]+|0x[0-9A-Fa-f]+|"[^"\\\n]*")$')

# What a setting can be, as Kconfig names its types.
TYPES = ("bool", "int", "hex", "string")

_INT = re.compile(r"^-?[0-9]+$")
_HEX = re.compile(r"^0x[0-9A-Fa-f]+$")


def symbol_of(name):
    """The Kconfig symbol for a library name: EE24 for ee24, ONE_WIRE for one-wire."""
    return re.sub(r"[^A-Za-z0-9]", "_", str(name)).upper()


def _symbol(text, where):
    """A symbol written in installer.yml, without CONFIG_ in front, or ManifestError."""
    found = str(text).strip()

    if found.startswith("CONFIG_"):
        found = found[len("CONFIG_"):]

    if not SYMBOL.match(found):
        raise ManifestError(
            f"{where} has {text!r}. Write a Kconfig symbol in capitals, digits and _, "
            "such as I2C or CONFIG_I2C."
        )

    return found


class Requirement:
    """A symbol the application has to have, and the value it needs: CONFIG_I2C=y."""

    def __init__(self, text):
        name, _, value = str(text).partition("=")
        self.symbol = _symbol(name, "requires.kconfig")
        self.value = value.strip() or "y"

        if not VALUE.match(self.value):
            raise ManifestError(
                f"requires.kconfig has {text!r}. Give a symbol, which is set to y, or "
                'SYMBOL=value, with y, n, a number, 0x and a hex number, or "text".'
            )

    @property
    def line(self):
        """The line in prj.conf."""
        return f"CONFIG_{self.symbol}={self.value}"

    def __repr__(self):
        return f"Requirement({self.line})"


class Peripheral:
    """Hardware the library uses, for the user to give it in the devicetree."""

    def __init__(self, data):
        data = data if isinstance(data, dict) else {"type": data}
        self.type = str(data.get("type", "")).lower()
        self.count = int(data.get("count", 1))
        self.note = str(data.get("note", "") or "")

    def describe(self):
        many = f" x{self.count}" if self.count > 1 else ""
        detail = f", {self.note}" if self.note else ""

        return f"{self.type.upper()}{many}{detail}"


class Setting:
    """
    One setting of the library, a Kconfig symbol the user sets in prj.conf.

    Written into the library's Kconfig, so the C code reads it as
    CONFIG_<name>. Everything is checked here, since all of it is written into
    a file Kconfig reads, and the manifest comes over the network.
    """

    def __init__(self, data, library_symbol):
        if not isinstance(data, dict):
            raise ManifestError("zephyr.settings holds one entry per setting, each with a name and a type.")

        self.name = _symbol(data.get("name", ""), "zephyr.settings")
        where = f"zephyr.settings {self.name}"

        if self.name == library_symbol:
            raise ManifestError(f"{where} is the library's own symbol. Give the setting a name of its own.")

        self.type = str(data.get("type", "")).lower()

        if self.type not in TYPES:
            raise ManifestError(f"{where} has type {data.get('type')!r}. Use one of: {', '.join(TYPES)}.")

        self.prompt_given = bool(data.get("prompt"))
        self.prompt = module.one_line(data.get("prompt") or self.name)
        self.help = [line.rstrip() for line in str(data.get("help") or "").strip().splitlines()]
        self.range = self._range(data.get("range"), where)

        if "default" not in data or data["default"] is None:
            raise ManifestError(f"{where} has no default. Every setting needs one, so it builds as it is.")

        self.default = self._value(data["default"], where)

    def _number(self, value, where):
        """An int or hex value as a number, for comparing with the range."""
        text = str(value).strip()

        if isinstance(value, bool) or not (_INT.match(text) or _HEX.match(text)):
            raise ManifestError(f"{where}: {value!r} is not a number.")

        return int(text, 0)

    def _range(self, value, where):
        """The smallest and largest the setting may be, or None."""
        if value is None:
            return None

        if self.type not in ("int", "hex"):
            raise ManifestError(f"{where} has a range, which only an int or a hex setting can have.")

        if not isinstance(value, list) or len(value) != 2:
            raise ManifestError(f"{where}: write the range as [smallest, largest].")

        low, high = (self._number(item, where) for item in value)

        if low > high:
            raise ManifestError(f"{where}: the range starts above where it ends.")

        return (low, high)

    def _value(self, value, where):
        """The default as Kconfig writes it."""
        if self.type == "bool":
            if value is True or str(value).lower() in ("y", "yes", "true"):
                return "y"

            if value is False or str(value).lower() in ("n", "no", "false"):
                return "n"

            raise ManifestError(f"{where}: the default of a bool is true or false, not {value!r}.")

        if self.type == "string":
            text = str(value)

            if "\n" in text:
                raise ManifestError(f"{where}: the default is one line of text.")

            return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'

        number = self._number(value, where)

        if self.range and not (self.range[0] <= number <= self.range[1]):
            raise ManifestError(f"{where}: the default {value} is outside its range.")

        return self.format(number)

    def format(self, number):
        """A number written the way this setting's type writes it."""
        return hex(number) if self.type == "hex" else str(number)

    @property
    def line(self):
        """The setting at its default, as a line of prj.conf."""
        return f"CONFIG_{self.name}={self.default}"

    def __repr__(self):
        return f"Setting({self.line})"


class ZephyrPart:
    """The zephyr section of installer.yml, with what it leaves out filled in."""

    def __init__(self, library, data):
        if data is None:
            data = {}

        if not isinstance(data, dict):
            raise ManifestError("zephyr should hold kconfig and settings.")

        self.symbol = _symbol(data["kconfig"], "zephyr.kconfig") if data.get("kconfig") else symbol_of(library.name)

        settings = data.get("settings") or []

        if not isinstance(settings, list):
            raise ManifestError("zephyr.settings is a list, one entry per setting.")

        self.settings = [Setting(entry, self.symbol) for entry in settings]
        names = [setting.name for setting in self.settings]
        twice = sorted({name for name in names if names.count(name) > 1})

        if twice:
            raise ManifestError(f"zephyr.settings has {', '.join(twice)} more than once.")

        # Lines of CMake the library needs beyond its files, written as they
        # stand into its module's CMakeLists.txt. They run when the user
        # configures the build, as a library's own module.yml would.
        cmake = data.get("cmake") or []

        if not isinstance(cmake, list) or not all(isinstance(line, str) for line in cmake):
            raise ManifestError("zephyr.cmake is a list of lines of CMake, each in quotes when it holds a colon.")

        if any("\n" in line or "\r" in line for line in cmake):
            raise ManifestError("zephyr.cmake has a line that runs onto another. Give each line on its own.")

        self.cmake = [line.strip() for line in cmake if line.strip()]


class Zephyr(Target):
    """A Zephyr application: CMakeLists.txt with find_package(Zephyr), and prj.conf."""

    name = "zephyr-installer"
    record_name = ".zephyr-installer.json"
    project = "Zephyr application"
    requires_key = "zephyr_installer"
    no_project = "No Zephyr application was recognised here, so nothing was registered."
    no_project_hint = "Run this from your application's folder, the one holding CMakeLists.txt and prj.conf."

    def __init__(self, version):
        self.version = version
        # The Kconfig file chosen for this run, by --conf or by the answer to
        # the question, which is asked once however many libraries go in.
        self.conf_given = None
        self.conf_chosen = None
        self.ask = None
        # The file each library of this run goes into, settled by check()
        # and used by integrate(), so the two always agree.
        self.conf_of = {}

    def add_arguments(self, parser):
        parser.add_argument(
            "--conf",
            default=None,
            metavar="FILE",
            help="the Kconfig file of the application that switches the library on, such as "
            "prj.conf or boards/nrf52840dk_nrf52840.conf. Asked when the application has more "
            "than one, prj.conf otherwise. A library already in one stays there.",
        )

    def take_arguments(self, args, ask):
        self.conf_given = getattr(args, "conf", None)
        self.ask = ask

    def default_folder(self, library):
        """Libraries go together in modules/ of the application."""
        return f"modules/{library.name}"

    def conf_for(self, library, project_root):
        """
        The Kconfig file this library's symbols go into, as a path from the
        application's folder.

        The one that already has its block, on an update. Otherwise the one
        given with --conf, or chosen earlier in this run. Otherwise, with more
        than one to choose from and someone to ask, the answer, and prj.conf
        when there is nobody or nothing to choose.
        """
        if library.name in self.conf_of:
            return self.conf_of[library.name]

        chosen = app.holding(project_root, library.name) or self.conf_given or self.conf_chosen

        if chosen is None:
            offered = app.conf_files(project_root)
            chosen = app.PRJ_CONF

            if len(offered) > 1 and self.ask is not None:
                print()
                print(console.note("This application has more than one Kconfig file: " + ", ".join(offered)))
                answer = self.ask(console.strong(f"Kconfig file for the libraries [{app.PRJ_CONF}]: "))
                chosen = answer or app.PRJ_CONF

            self.conf_chosen = chosen

        chosen = Path(chosen).as_posix()
        self.conf_of[library.name] = chosen

        return chosen

    def read_manifest(self, manifest, data):
        manifest.zephyr = ZephyrPart(manifest, data.get("zephyr"))

    def read_requirements(self, requirements, data):
        """The Zephyr part of requires: Kconfig symbols, and hardware."""
        kconfig = data.get("kconfig") or []

        if not isinstance(kconfig, list):
            raise ManifestError("requires.kconfig is a list of symbols, such as [I2C].")

        requirements.kconfig = [Requirement(entry) for entry in kconfig]
        requirements.peripherals = [Peripheral(entry) for entry in (data.get("peripherals") or [])]

    def requirements_empty(self, requirements):
        return not (requirements.kconfig or requirements.peripherals)

    def warnings(self, manifest):
        part = getattr(manifest, "zephyr", None)
        found = []

        for setting in (part.settings if part else []):
            if not setting.name.startswith(part.symbol + "_"):
                found.append(f"zephyr.settings {setting.name} does not start with {part.symbol}_, "
                             "so it may be taken by another library")

            if not setting.prompt_given:
                found.append(f"zephyr.settings {setting.name} has no prompt, so menuconfig shows only its name")

        return found

    def check(self, library, project_root):
        """What the application is missing for this library. Never stops an install."""
        findings = []

        if app.find_cmakelists(project_root) is None:
            findings.append(Finding(
                WARN, "No CMakeLists.txt with find_package(Zephyr) here",
                "Run this from your application's folder, or give it with --project.",
            ))

            return findings

        conf = self.conf_for(library, project_root)
        assigned = app.assigned(project_root, library.name, conf)
        ours = app.in_block(project_root, library.name, conf)

        for symbol, value, line in app.wanted(library):
            have = assigned.get(symbol)

            # The library's own switch is no requirement, and is only worth a
            # line when the user has set it already.
            if symbol == library.zephyr.symbol and have is None:
                continue

            if have is None and ours.get(symbol) == value:
                findings.append(Finding(OK, f"{line} is in {conf}"))
            elif have is None:
                findings.append(Finding(INFO, f"{line} goes into {conf}"))
            elif have[0] == value:
                # The same, so nothing is wrong, but the block will not set it,
                # and the user should know which line does.
                findings.append(Finding(
                    WARN, f"{have[1]} already sets {line}, so the block has it commented out",
                    "Your line is the one used. Nothing to do.",
                ))
            else:
                findings.append(Finding(
                    WARN, f"{have[1]} sets CONFIG_{symbol}={have[0]}, and {library.name} needs {value}. "
                    "The block has it commented out",
                    "Your line is the one used. Change it if the library is to work.",
                ))

        for peripheral in library.requires.peripherals:
            findings.append(Finding(
                INFO, f"Needs {peripheral.describe()}",
                "Enable it in your board's devicetree, or in an overlay of the application.",
            ))

        return findings

    def integrate(self, project_root, library, destination, only=None, dropped=(),
                  dropped_defines=()):
        """
        Make the library a module of the application, and switch it on.

        dropped and dropped_defines need nothing here: the module's files are
        written again from the new manifest on every install, so a file or a
        define that has gone is simply no longer in them.
        """
        outcomes = [module.write(library, destination)]
        outcomes.extend(app.integrate(project_root, library, destination,
                                      self.conf_for(library, project_root)))

        return outcomes

    def uninstall(self, project_root, library):
        """
        Take the library out of the application's CMakeLists.txt and Kconfig
        file, and delete the module files this wrote into its folder.
        """
        defined = module.symbols(library.destination) if library.destination is not None else []
        outcomes = app.uninstall(project_root, library.name)

        if library.destination is not None:
            saved = module.remove(library.destination)

            if saved is not None:
                outcomes.append(Outcome(
                    module.NAME, CHANGED,
                    f"Your lines in zephyr/CMakeLists.txt are saved, in zephyr/{saved.name}.",
                    backup=saved,
                ))

        # A setting the user set below the block names a symbol that is gone
        # now, and Zephyr stops on a symbol it does not know. The line is the
        # user's, so it is named rather than taken out.
        for conf, lines in app.leftover(project_root, defined).items():
            outcomes.append(Outcome(
                conf, MANUAL,
                f"{conf} still sets what came with {library.name}, and Zephyr stops on a symbol it "
                "does not know. Take these lines out:",
                lines,
            ))

        return outcomes
