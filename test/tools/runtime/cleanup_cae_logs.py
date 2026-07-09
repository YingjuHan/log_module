#!/usr/bin/env python3
"""Directory-level retention helper for CAE log artifacts."""

from __future__ import annotations

import argparse
import os
import time


LOG_SUFFIXES = (".log", ".jsonl")


def collect_candidates(target_dir: str) -> list[dict[str, object]]:
    """Collect log-like files from a directory."""
    candidates: list[dict[str, object]] = []
    for name in sorted(os.listdir(target_dir)):
        path = os.path.join(target_dir, name)
        if not os.path.isfile(path):
            continue
        if not name.endswith(LOG_SUFFIXES):
            continue
        stat = os.stat(path)
        candidates.append({
            "path": path,
            "name": name,
            "size": stat.st_size,
            "mtime": stat.st_mtime,
        })
    return candidates


def select_deletions(
    files: list[dict[str, object]],
    older_than_days: float | None = None,
    max_total_size_gb: float | None = None,
) -> list[dict[str, object]]:
    """Select files that would be deleted by the retention rules."""
    selected: list[dict[str, object]] = []
    kept = list(files)
    now = time.time()

    if older_than_days is not None:
        cutoff = now - (older_than_days * 86400)
        expired = [item for item in kept if float(item["mtime"]) < cutoff]
        selected.extend(expired)
        kept = [item for item in kept if float(item["mtime"]) >= cutoff]

    if max_total_size_gb is not None:
        max_bytes = int(max_total_size_gb * 1024 * 1024 * 1024)
        kept_sorted = sorted(kept, key=lambda item: float(item["mtime"]))
        total_size = sum(int(item["size"]) for item in kept_sorted)
        while total_size > max_bytes and kept_sorted:
            item = kept_sorted.pop(0)
            selected.append(item)
            total_size -= int(item["size"])

    unique: dict[object, dict[str, object]] = {}
    for item in selected:
        unique[item["path"]] = item
    return sorted(unique.values(), key=lambda item: float(item["mtime"]))


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Cleanup CAE log directory")
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    parser.add_argument("--target-dir", default=os.path.join(project_root, "logs"))
    parser.add_argument("--older-than-days", type=float)
    parser.add_argument("--max-total-size-gb", type=float)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if not os.path.isdir(args.target_dir):
        raise SystemExit(f"Target directory not found: {args.target_dir}")
    if args.older_than_days is None and args.max_total_size_gb is None:
        raise SystemExit("Specify at least one retention rule.")

    files = collect_candidates(args.target_dir)
    deletions = select_deletions(
        files,
        older_than_days=args.older_than_days,
        max_total_size_gb=args.max_total_size_gb,
    )

    total_size = sum(int(item["size"]) for item in files)
    delete_size = sum(int(item["size"]) for item in deletions)
    mode = "apply" if args.apply else "dry-run"
    print(f"Mode: {mode}")
    print(f"Scanned {len(files)} candidate file(s) in {os.path.abspath(args.target_dir)}")
    print(f"Selected {len(deletions)} file(s) for deletion, reclaiming {delete_size} bytes")

    for item in deletions:
        print(
            f"{item['name']}\t{item['size']}\t"
            f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(float(item['mtime'])))}"
        )
        if args.apply:
            os.remove(str(item["path"]))

    remaining = total_size - delete_size if args.apply else total_size
    print(f"Directory size before: {total_size} bytes")
    print(f"Directory size after {mode}: {remaining} bytes")


if __name__ == "__main__":
    main()
