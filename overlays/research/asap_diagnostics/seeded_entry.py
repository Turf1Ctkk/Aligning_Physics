"""Seed before environment/model construction; preserve IsaacGym import order."""
import argparse
import os
from pathlib import Path
import runpy
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("train", "eval"))
    parser.add_argument("--rng-seed", type=int, required=True)
    args, overrides = parser.parse_known_args()
    root = Path(__file__).resolve().parents[2]
    os.chdir(root)
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "humanoidverse"))
    import isaacgym  # noqa: F401 -- must precede torch
    from humanoidverse.utils.common import seeding
    seeding(args.rng_seed, torch_deterministic=False)
    script = root / "humanoidverse" / ("train_agent.py" if args.mode == "train" else "eval_agent.py")
    sys.argv = [str(script)] + overrides
    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()
