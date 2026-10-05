#!/usr/bin/env python3
"""Build offline evaluation cases from the raw corpus.

One case per reviewed PR. A case contains the diff as it looked at the
commit the reviewer commented on most (the "snapshot"), the PR title and
description, and the ground truth: the reviewer's inline comments at that
snapshot (file, line, body) plus comments from other review rounds for
reference.

Reads ``corpus/raw/``; writes ``eval/cases/<repo>_pr<N>.json``.
Python 3.9+, no third-party packages.
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reviewer", default="keewis")
    ap.add_argument("--raw", default=Path(__file__).parent.parent / "corpus" / "raw", type=Path)
    ap.add_argument("--out", default=Path(__file__).parent / "cases", type=Path)
    ap.add_argument("--min-comments", type=int, default=2,
                    help="skip PRs with fewer ground-truth comments at the snapshot")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    for meta_file in glob.glob(str(args.raw / "diffs" / "*_pr_meta.json")):
        slug = Path(meta_file).name[: -len("_pr_meta.json")]
        meta = json.loads(Path(meta_file).read_text())
        comments: list = []
        for f in sorted(glob.glob(str(args.raw / f"{slug}_comments_*.json"))):
            comments += [c for c in json.loads(Path(f).read_text()) if c["user"]["login"] == args.reviewer]
        pulls = {}
        for f in glob.glob(str(args.raw / f"{slug}_pulls_*.json")):
            for p in json.loads(Path(f).read_text()):
                pulls[p["number"]] = p
        for f in glob.glob(str(args.raw / f"{slug}_pull_*.json")):
            p = json.loads(Path(f).read_text())
            pulls[p["number"]] = p

        by_pr = collections.defaultdict(list)
        for c in comments:
            by_pr[int(c["pull_request_url"].rsplit("/", 1)[1])].append(c)

        n_written = 0
        for n_str, m in meta.items():
            n = int(n_str)
            snap = m["snapshot_commit"]
            diff_file = args.raw / "diffs" / f"{slug}_pr{n}_{snap[:8]}.diff"
            if not diff_file.exists():
                continue
            at_snap = [c for c in by_pr[n] if c["original_commit_id"] == snap]
            if len(at_snap) < args.min_comments:
                continue
            other = [c for c in by_pr[n] if c["original_commit_id"] != snap]
            pr = pulls.get(n, {})

            def gt(c):
                return {
                    "path": c["path"],
                    "line": c.get("original_line") or c.get("line"),
                    "side": c.get("side"),
                    "body": c["body"],
                    "diff_hunk": c.get("diff_hunk"),
                    "created_at": c["created_at"],
                    "url": c["html_url"],
                }

            case = {
                "id": f"{slug}_pr{n}",
                "repo": m.get("repo") or pr.get("base", {}).get("repo", {}).get("full_name"),
                "pr": n,
                "title": pr.get("title") or m.get("title"),
                "body": pr.get("body") or "",
                "snapshot_commit": snap,
                "base_sha": m["base_sha"],
                "diff": diff_file.read_text(errors="replace"),
                "ground_truth": [gt(c) for c in sorted(at_snap, key=lambda c: (c["path"], c.get("original_line") or 0))],
                "other_rounds": [gt(c) for c in other],
            }
            (args.out / f"{case['id']}.json").write_text(json.dumps(case, indent=1, ensure_ascii=False))
            n_written += 1
            print(f"{case['id']:<22} {len(case['ground_truth']):>2} ground-truth comments, "
                  f"{len(case['diff']) // 1000:>3} kB diff  {case['title'][:50]}")
        print(f"{slug}: {n_written} cases written to {args.out}")


if __name__ == "__main__":
    main()
