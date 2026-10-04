"""Run from the checkout after installing .[dev]; output must be caller selected."""

import argparse
from pathlib import Path

from stmtconv.demo import generate

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    for layout in ["separate", "signed", "card"]:
        generate(args.folder, layout=layout)
        generate(args.folder, layout=layout, scanned=True)
