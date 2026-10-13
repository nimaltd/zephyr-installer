"""
Install embedded C libraries into a Zephyr application.

Installed with pip, it is the zephyr-installer command. It takes a library from
GitHub, from a downloaded zip, or from a folder, makes it a Zephyr module of the
application, and switches it on in prj.conf.

The work that is the same for any project is the shared core, in core/, from
github.com/nimaltd/core-installer. What a Zephyr application is, is in zephyr.py.

See https://github.com/nimaltd/zephyr-installer
"""

__version__ = "1.0.0"

# Before anything of the core is used: it asks the target for every answer
# that depends on the kind of project.
from .core import target as _target  # noqa: E402
from .zephyr import Zephyr  # noqa: E402

_target.use(Zephyr(__version__))

from .core.installer import InstallError, Result, install_in_place, install_to  # noqa: E402
from .core.manifest import Manifest, ManifestError, load  # noqa: E402

__all__ = [
    "InstallError",
    "Manifest",
    "ManifestError",
    "Result",
    "install_in_place",
    "install_to",
    "load",
    "main",
]


def main(argv=None):
    """Run the command line interface. Imported lazily to keep start-up cheap."""
    from .cli import main as _main

    return _main(argv=argv)
