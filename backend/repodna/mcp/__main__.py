"""Executable module entrypoint for `python -m repodna.mcp`."""

from repodna.mcp.server import main

if __name__ == "__main__":
    raise SystemExit(main())
