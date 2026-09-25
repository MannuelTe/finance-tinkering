"""Run the CLI without relying on the editable install (see README: hidden .pth files)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from taxharvest.cli import main

if __name__ == "__main__":
    main()
