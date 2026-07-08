#!/usr/bin/env python3
"""Copy Eval_Data/Traces and Eval_Data/Observations to a timestamped backup folder.

Optional ``--include-baselines`` also copies ``Eval_Data/Baselines/Traces`` and
``Eval_Data/Baselines/Observations`` into ``<dest>/Baselines/{Traces,Observations}``.
"""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path


def _copy_subdirs(src_root: Path, dest_root: Path, subs: tuple[str, ...]) -> list[str]:
    """Copy each existing subdirectory under ``src_root`` into ``dest_root``.

    Refuses to overwrite when the target subdir already exists. Returns absolute
    paths of the targets that were created.
    """
    copied: list[str] = []
    for sub in subs:
        src = src_root / sub
        if not src.exists():
            continue
        target = dest_root / sub
        if target.exists():
            raise SystemExit(f"Refusing to overwrite existing backup path: {target}")
        shutil.copytree(src, target)
        copied.append(str(target))
    return copied


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dest",
        type=str,
        default=None,
        help="Full backup directory path (default: Eval_Data/backups/pre-faithfulness-replay_<UTC>)",
    )
    parser.add_argument(
        "--root",
        type=str,
        default=None,
        help="Repository root (default: parent of scripts/)",
    )
    parser.add_argument(
        "--include-baselines",
        action="store_true",
        help="Also copy Eval_Data/Baselines/{Traces,Observations} into <dest>/Baselines/.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parent.parent
    eval_data = root / "Eval_Data"
    if args.dest:
        dest = Path(args.dest).resolve()
    else:
        # Include milliseconds to avoid collisions on repeated runs.
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")[:-4] + "Z"
        ts_safe = ts.replace(".", "")
        dest = eval_data / "backups" / f"pre-faithfulness-replay_{ts_safe}"

    dest.mkdir(parents=True, exist_ok=True)
    copied = _copy_subdirs(eval_data, dest, ("Traces", "Observations"))

    if args.include_baselines:
        baselines_src = eval_data / "Baselines"
        if not baselines_src.exists():
            raise SystemExit(
                f"--include-baselines: source not found: {baselines_src}"
            )
        baselines_dest = dest / "Baselines"
        baselines_dest.mkdir(parents=True, exist_ok=True)
        copied += _copy_subdirs(baselines_src, baselines_dest, ("Traces", "Observations"))

    if not copied:
        raise SystemExit(f"No Traces/ or Observations/ found under {eval_data}")

    print(dest)


if __name__ == "__main__":
    main()
