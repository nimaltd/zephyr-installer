"""Lets the package be run directly: python -m zephyr_installer owner/example"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
