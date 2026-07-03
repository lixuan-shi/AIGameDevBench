#!/usr/bin/env python
"""Audit testcase health from a source checkout.

This wrapper keeps the old script entrypoint working; the canonical audit logic
lives in :mod:`aigamedevbench.testcase_audit` and is also exposed as
``aigdbench audit``.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from aigamedevbench.testcase_audit import (  # noqa: E402
    audit_testcases,
    format_audit_table,
    select_testcases,
    write_health_json,
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--testcases-dir", default="./testcases", type=Path)
    ap.add_argument("--godot-binary", default="godot")
    ap.add_argument("--repo-root", default=".", type=Path,
                    help="fallback repo for git-type cases without an explicit source_repo")
    ap.add_argument("--only", action="append", default=None,
                    help="audit only these testcase ids (repeatable)")
    ap.add_argument("--json", type=Path, default=None,
                    help="write the machine-readable health snapshot here")
    args = ap.parse_args()

    rows = audit_testcases(
        select_testcases(args.testcases_dir.resolve(), args.only),
        args.repo_root.resolve(),
        args.godot_binary,
    )
    print(format_audit_table(rows))
    if args.json:
        write_health_json(args.json, rows)
        print(f"wrote {args.json}", file=sys.stderr)
    return 0 if all(row["healthy"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
