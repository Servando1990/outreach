from __future__ import annotations

import sys

from automation.main import main


if __name__ == "__main__":
    raise SystemExit(main(["backfill", *sys.argv[1:]]))
