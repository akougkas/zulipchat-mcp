#!/usr/bin/env uv run python
"""
Legacy interactive test script for ZulipChat MCP Agent Communication System.
Moved from scripts/ to examples/ as part of repository consolidation.

Run with:
  uv run examples/test_mcp_tools_legacy.py
  uv run examples/test_mcp_tools_legacy.py --interactive
"""

from pathlib import Path
import sys


def main() -> None:
    here = Path(__file__).resolve()
    scripts_version = here.parent.parent / "scripts" / "test_mcp_tools.py"
    print("This legacy example has been moved.")
    print("If you still need the old test harness, run:")
    print(f"  uv run {scripts_version}")


if __name__ == "__main__":
    main()


