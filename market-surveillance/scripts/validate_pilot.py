"""Compatibility wrapper for ``marketsurv validate-pull``."""

import sys

from marketsurv.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["validate-pull", *sys.argv[1:]]))
