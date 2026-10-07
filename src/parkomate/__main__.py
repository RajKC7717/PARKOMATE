"""``python -m parkomate`` entry point."""

from __future__ import annotations

import sys

from parkomate.cli import main

if __name__ == "__main__":
    sys.exit(main())
