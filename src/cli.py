"""
The zephyr-installer command: the core's command line, with the Zephyr target.

The target is chosen when the package is imported, before this runs. --conf,
the one option of zephyr-installer's own, comes from the target too.
"""

import sys

from .core.cli import main

__all__ = ["main"]

if __name__ == "__main__":
    sys.exit(main())
