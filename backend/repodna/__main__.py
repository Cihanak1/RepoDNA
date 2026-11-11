"""Entrypoint when invoked via `python -m repodna`."""

from __future__ import annotations

import sys

from repodna.cli.main import main

if __name__ == "__main__":
    sys.exit(main())
