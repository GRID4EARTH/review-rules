#!/usr/bin/env python3
"""Compare static review results with the reviewer's actual comments.

Produces ``eval/results/report.md`` with, per PR:

* each ground-truth comment and the model finding (if any) anchored to the
  same file within ``--window`` lines,
* model findings with no nearby ground-truth comment (false-positive
  candidates),
* counts.

Location matching is only a first filter. Whether a matched pair says the
*same thing* has to be judged by a person reading the table; that is the
point of this report. Python 3.9+, no third-party packages.
"""
from __future__ import annotations

import argparse
import collections
import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def short(s: str, n: int = 160) -> str:
    s = " ".join((s or "").split())
    return (s[: n - 1] + "…") if len(s) > n else s


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cases", type=Path, default=ROOT / "eval" / "cases")
    ap.add_argument("--results", type=Path, default=ROOT / "eval" / "results")
    ap.add_argument("--window", type=int, default=6, help="line distance counted as the same location")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    out = args.out or (args.results / "report.md")

    results = {p.stem: json.loads(p.read_text()) for p in sorted(args.results.glob("*.json"))}
    cases = {p.stem: json.loads(p.read_text()) for p in sorted(args.cases.glob("*.json"))}
    if not results:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("# Eval report\n\nNo results yet. Run `eval/run_review.py` first.\n")
        print(f"no results in {args.results}; wrote placeholder {out}")
        return

    lines = ["# Eval report: static reviewer vs. actual review comments", ""]
    totals = collections.Counter()
    rule_counter: collections.Counter = collections.Counter()
    sev_counter: collections.Counter = collections.Counter()

    for cid, res in results.items():
        case = cases.get(cid)
        if case is None:
            lines.append(f"## {cid}\n\nno matching case file\n")
            continue
        gts = case["ground_truth"]
        finds = res.get("findings", [])
        for f in finds:
            rule_counter.update(f.get("rule_ids", []))
            sev_counter[f.get("severity", "?")] += 1

        matched_f: set = set()
        rows = []
        for gt in gts:
            best, best_d = None, None
            for i, f in enumerate(finds):
                if i in matched_f or f.get("path") != gt["path"]:
                    continue
                d = abs(int(f.get("line") or 0) - int(gt.get("line") or 0))
                if d <= args.window and (best_d is None or d < best_d):
                    best, best_d = i, d
            if best is not None:
                matched_f.add(best)
            rows.append((gt, finds[best] if best is not None else None))

        hit = sum(1 for _, f in rows if f is not None)
        totals["gt"] += len(gts)
        totals["hit"] += hit
        totals["findings"] += len(finds)
        totals["unmatched_findings"] += len(finds) - len(matched_f)

        lines.append(f"## {cid}: {case['title']}")
        lines.append("")
        lines.append(f"- model: `{res.get('model')}`, effort {res.get('effort')}, {res.get('elapsed_s')} s, "
                     f"verdict: **{res.get('verdict')}**")
        lines.append(f"- ground truth: {len(gts)} comments; model: {len(finds)} findings; "
                     f"same-location matches: {hit}/{len(gts)}; findings without ground truth nearby: "
                     f"{len(finds) - len(matched_f)}")
        if res.get("summary"):
            lines.append(f"- model summary: {short(res['summary'], 300)}")
        if res.get("parse_error"):
            lines.append(f"- **parse error**: {res['parse_error']}")
        lines.append("")
        lines.append("| location | actual comment | model finding |")
        lines.append("|---|---|---|")
        for gt, f in rows:
            loc = f"`{gt['path'].split('/')[-1]}` L{gt['line']}"
            model_cell = "—" if f is None else f"[{', '.join(f.get('rule_ids', []))}] {short(f.get('comment'))}"
            lines.append(f"| {loc} | {short(gt['body'])} | {model_cell} |")
        extra = [f for i, f in enumerate(finds) if i not in matched_f]
        if extra:
            lines.append("")
            lines.append("Model findings with no actual comment nearby (false-positive candidates, "
                         "or things the reviewer let slide):")
            lines.append("")
            for f in extra:
                lines.append(f"- `{str(f.get('path', '')).split('/')[-1]}` L{f.get('line')} "
                             f"[{', '.join(f.get('rule_ids', []))}] {f.get('severity')}: {short(f.get('comment'), 220)}")
        lines.append("")

    lines.insert(2, textwrap.dedent(f"""
        **Totals over {len(results)} PRs**: {totals['gt']} actual comments, {totals['findings']} model findings,
        {totals['hit']} same-location matches ({(100 * totals['hit'] / max(1, totals['gt'])):.0f}% of actual
        comments have a model finding within {args.window} lines), {totals['unmatched_findings']} model findings
        with nothing nearby.

        Rule ids used by the model: {', '.join(f'{k} ×{v}' for k, v in rule_counter.most_common())}
        Severities: {', '.join(f'{k} ×{v}' for k, v in sev_counter.most_common())}

        Read each table row and decide whether the two cells make the same point. A same-location match
        with a different point is a miss; a finding with nothing nearby can still be a valid comment the
        reviewer did not make. Record decisions in the rubric (add, sharpen or delete rules), then re-run.
        """).strip() + "\n")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines))
    print(f"wrote {out}: {totals['hit']}/{totals['gt']} same-location matches over {len(results)} PRs")


if __name__ == "__main__":
    main()
