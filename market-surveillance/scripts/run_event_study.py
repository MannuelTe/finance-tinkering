"""Compatibility wrapper for ``marketsurv analyze``."""

import sys

from marketsurv.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["analyze", *sys.argv[1:]]))
