#!/usr/bin/env python3
"""Deterministic checks for the mechanical subset of the review rubric.

These need no model and can run in pre-commit or CI. They are heuristics:
each finding names the rubric rule so a false positive can be judged quickly.

Rules covered (ids from rubric/REVIEW_RUBRIC.md):

* D3  all-caps indexing scheme names (NESTED / RING / ZUNIQ) in prose and comments
      (reported as "suggestion": a maintainer preference, it does not affect the exit status)
* C1  more than two top-level test functions for the same target not grouped in a class
* B2  rayon parallel iterators used outside the ``maybe_parallelize!`` definition
* B1  Python-side ``raise ValueError`` for a parameter whose Rust binding already validates
      (reported as "check", since the Rust side cannot be resolved textually)
* D5  Markdown page that contains only a heading (placeholder page)
* D8  Rust doc comment referencing a source path such as ``js/src/foo.rs``
* A9  hand-written degree/radian conversion helpers in Rust
* D11 non-English MyST toctree captions

Not covered on purpose: the D1 docstring format (section headers, ``Examples``
section) is left to a numpydoc linter such as ``numpydoc validate``.

Usage::

    python static-checks/check_rubric_static.py [paths...]   # default: repository root
    python static-checks/check_rubric_static.py --changed    # only files changed vs. main

Exit status 1 when any finding other than a suggestion is reported, so it can gate CI if wanted.
Python 3.9+, no third-party packages.
"""
from __future__ import annotations

import argparse
import collections
import re
import subprocess
import sys
from pathlib import Path

SUGGESTION_RULES = {"D3"}
SKIP_DIRS = {".git", "target", "node_modules", ".pixi", "pkg", "dist", "build", "_build", "generated",
             "review-agent"}


def iter_files(paths, suffixes):
    for p in paths:
        p = Path(p)
        if p.is_file():
            if p.suffix in suffixes:
                yield p
            continue
        for f in p.rglob("*"):
            if f.is_file() and f.suffix in suffixes and not (SKIP_DIRS & set(f.parts)):
                yield f


def read(p: Path) -> str:
    try:
        return p.read_text(errors="replace")
    except OSError:
        return ""


class Report:
    def __init__(self):
        self.findings = []

    def add(self, rule, path, line, msg):
        self.findings.append((rule, str(path), line, msg))


def check_caps_scheme(paths, rep):
    pat = re.compile(r"\b(NESTED|RING|ZUNIQ)\b")
    for f in iter_files(paths, {".md", ".rst", ".py", ".rs", ".ts"}):
        for i, line in enumerate(read(f).splitlines(), 1):
            s = line.strip()
            # only prose / comments / docstrings, not code identifiers like `Scheme::RING`
            if f.suffix in {".md", ".rst"} or s.startswith(("#", "//", "///", "//!", "*", "/*")) or '"""' in s:
                if "::" in line or "Scheme." in line:
                    continue
                m = pat.search(line)
                if m:
                    rep.add("D3", f, i, f"'{m.group(1)}' spelled all-caps; the scheme names are English words")


def check_test_grouping(paths, rep):
    for f in iter_files(paths, {".py"}):
        if not f.name.startswith("test_"):
            continue
        groups = collections.defaultdict(list)
        for i, line in enumerate(read(f).splitlines(), 1):
            m = re.match(r"def test_([a-z0-9]+(?:_[a-z0-9]+)?)", line)  # top-level only (no indent)
            if m:
                groups[m.group(1)].append(i)
        for target, ls in groups.items():
            if len(ls) > 2:
                rep.add("C1", f, ls[0], f"{len(ls)} top-level tests share the prefix 'test_{target}'; group them in a Test class")


def check_parallelism(paths, rep):
    pat = re.compile(r"\.(par_iter|into_par_iter|par_chunks(?:_mut)?|par_bridge)\(")
    for f in iter_files(paths, {".rs"}):
        text = read(f)
        if "macro_rules! maybe_parallelize" in text:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if pat.search(line):
                rep.add("B2", f, i, "rayon used directly; vectorised code should go through maybe_parallelize!")


def check_python_validation(paths, rep):
    """Flag Python wrappers that validate string options the Rust side is likely to validate too."""
    for f in iter_files(paths, {".py"}):
        if "tests" in f.parts:
            continue
        for i, line in enumerate(read(f).splitlines(), 1):
            if re.search(r"if \w+ not in \(.*\):", line):
                rep.add("B1", f, i, "check: string option validated in Python; if the Rust binding parses it too, drop one of them")


def check_placeholder_pages(paths, rep):
    for f in iter_files(paths, {".md"}):
        if f.name.lower() in {"readme.md", "license.md", "changelog.md"}:
            continue
        body = [l for l in read(f).splitlines() if l.strip() and not l.startswith("#") and not l.startswith("---")]
        if not body and read(f).strip():
            rep.add("D5", f, 1, "page has a heading but no content; remove or hide it until there is content")


def check_rust_doc_paths(paths, rep):
    pat = re.compile(r"`?(?:js|rust|python)/[\w./-]+\.rs`?")
    for f in iter_files(paths, {".rs"}):
        for i, line in enumerate(read(f).splitlines(), 1):
            if line.lstrip().startswith(("///", "//!")) and pat.search(line):
                rep.add("D8", f, i, "doc comment references a source path; use the crate path instead")


def check_angle_helpers(paths, rep):
    pat = re.compile(r"fn (degrees_to_radians|radians_to_degrees|deg2rad|rad2deg)\b")
    for f in iter_files(paths, {".rs"}):
        for i, line in enumerate(read(f).splitlines(), 1):
            m = pat.search(line)
            if m:
                rep.add("A9", f, i, f"'{m.group(1)}' reimplements f64::to_radians / to_degrees")


def check_toctree_captions(paths, rep):
    non_english = re.compile(r"caption:\s*(Guide utilisateur|Référence|Tutoriels|Exemples)", re.I)
    for f in iter_files(paths, {".md", ".rst"}):
        for i, line in enumerate(read(f).splitlines(), 1):
            if non_english.search(line):
                rep.add("D11", f, i, "non-English toctree caption")


CHECKS = [check_caps_scheme, check_test_grouping, check_parallelism, check_python_validation, check_placeholder_pages,
          check_rust_doc_paths, check_angle_helpers, check_toctree_captions]


def changed_files(base: str = "main"):
    out = subprocess.run(["git", "diff", "--name-only", f"{base}...HEAD"], capture_output=True, text=True)
    files = [Path(l) for l in out.stdout.splitlines() if l.strip()]
    return [f for f in files if f.exists()]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="files or directories (default: repository root)")
    ap.add_argument("--changed", action="store_true", help="only files changed relative to --base")
    ap.add_argument("--base", default="main")
    ap.add_argument("--only", help="comma-separated rule ids to report, e.g. D1,C1")
    args = ap.parse_args()

    if args.changed:
        paths = changed_files(args.base)
        if not paths:
            print("no changed files")
            return
    else:
        paths = args.paths or ["."]

    rep = Report()
    for check in CHECKS:
        check(paths, rep)
    only = set(args.only.split(",")) if args.only else None
    findings = sorted(f for f in rep.findings if only is None or f[0] in only)
    for rule, path, line, msg in findings:
        kind = " suggestion:" if rule in SUGGESTION_RULES else ""
        print(f"{path}:{line}: [{rule}]{kind} {msg}")
    by_rule = collections.Counter(f[0] for f in findings)
    print(f"\n{len(findings)} findings" + (": " + ", ".join(f"{k} ×{v}" for k, v in sorted(by_rule.items())) if findings else ""))
    sys.exit(1 if any(f[0] not in SUGGESTION_RULES for f in findings) else 0)


if __name__ == "__main__":
    main()
