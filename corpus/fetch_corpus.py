#!/usr/bin/env python3
"""Fetch the review corpus of one GitHub user from one or more repositories.

Writes raw GitHub API pages under ``corpus/raw/`` so that ``build_corpus.py``
and ``eval/build_cases.py`` can work offline afterwards.

What is fetched per repository:

* ``pulls/comments``            inline review comments (all authors, filtered later)
* ``issues/comments``           PR conversation + issue comments
* ``pulls?state=all``           PR metadata (title, body, base sha)
* ``pulls/{n}``                 metadata for PRs older than the list covers
* ``pulls/{n}/reviews``         review summaries (approve / request changes bodies)
* ``compare/{base}...{sha}.diff`` the diff as it looked when the reviewer commented
  (fetched from github.com, which does not count against the API rate limit)

Authentication: set ``GITHUB_TOKEN``, or have an authenticated ``gh`` CLI on PATH
(or point ``GH_BIN`` at one); the script then uses ``gh auth token`` (5000
requests/hour). Unauthenticated use is limited to 60 requests/hour and will stop
with a clear message when exhausted.
Existing files are skipped unless ``--force`` is given, so the script can be
re-run to resume.

Usage::

    python corpus/fetch_corpus.py --repo grid4earth/healpix-geo --repo xarray-contrib/xdggs \
        --reviewer keewis --out corpus/raw
"""
from __future__ import annotations

import argparse
import collections
import http.client
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.github.com"
WEB = "https://github.com"


_TOKEN: str | None = None


def _token() -> str | None:
    """GITHUB_TOKEN / GH_TOKEN, else the token of an authenticated ``gh`` CLI."""
    global _TOKEN
    if _TOKEN is None:
        _TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
        if not _TOKEN:
            import shutil
            import subprocess
            gh = os.environ.get("GH_BIN") or shutil.which("gh")
            if gh:
                r = subprocess.run([gh, "auth", "token"], capture_output=True, text=True)
                if r.returncode == 0 and r.stdout.strip():
                    _TOKEN = r.stdout.strip()
                    print("using the token of the authenticated gh CLI", file=sys.stderr)
    return _TOKEN or None


def _headers() -> dict:
    h = {"Accept": "application/vnd.github+json", "User-Agent": "review-corpus-fetcher"}
    tok = _token()
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def get(url: str, raw: bool = False, attempts: int = 4):
    """GET with retries for truncated / dropped connections (large pages through proxies)."""
    req = urllib.request.Request(url, headers=_headers())
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
                remaining = r.headers.get("X-RateLimit-Remaining")
                if remaining is not None and int(remaining) < 3:
                    reset = int(r.headers.get("X-RateLimit-Reset", "0"))
                    wait = max(0, reset - int(time.time()))
                    sys.exit(f"GitHub API rate limit nearly exhausted; resets in {wait // 60} min. "
                             "Set GITHUB_TOKEN and re-run to resume.")
                return data if raw else json.loads(data)
        except urllib.error.HTTPError as e:
            if e.code == 403 and "rate limit" in e.read().decode(errors="ignore").lower():
                sys.exit("GitHub API rate limit exhausted. Set GITHUB_TOKEN and re-run to resume.")
            raise
        except (http.client.IncompleteRead, urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt == attempts:
                data = _curl(url)  # last resort: some proxies truncate urllib responses but not curl's
                if data is None:
                    raise
                return data if raw else json.loads(data)
            print(f"  retry {attempt}/{attempts - 1} after {type(e).__name__} for {url.split('?')[0]}", file=sys.stderr)
            time.sleep(2 * attempt)


def _curl(url: str):
    import shutil
    import subprocess
    if not shutil.which("curl"):
        return None
    cmd = ["curl", "-sSfL", "--retry", "5", "--retry-all-errors", "--max-time", "180"]
    for k, v in _headers().items():
        cmd += ["-H", f"{k}: {v}"]
    r = subprocess.run(cmd + [url], capture_output=True)
    if r.returncode != 0:
        print(f"  curl fallback failed: {r.stderr.decode(errors='ignore').strip()[:200]}", file=sys.stderr)
        return None
    print(f"  fetched via curl fallback: {url.split('?')[0]}", file=sys.stderr)
    return r.stdout


def paginate(path: str, out: Path, prefix: str, force: bool, per_page: int = 100, max_pages: int = 0) -> list:
    """Fetch all pages (or up to ``max_pages``) of a list endpoint into ``<prefix>_<page>.json``."""
    items: list = []
    page = 1
    while not max_pages or page <= max_pages:
        f = out / f"{prefix}_{page}.json"
        if f.exists() and not force:
            data = json.loads(f.read_text())
        else:
            sep = "&" if "?" in path else "?"
            data = get(f"{API}{path}{sep}per_page={per_page}&page={page}")
            f.write_text(json.dumps(data))
            print(f"  {prefix} page {page}: {len(data)}")
        if not isinstance(data, list) or not data:
            break
        items += data
        if len(data) < per_page:
            break
        page += 1
    return items


def slug(repo: str) -> str:
    return repo.split("/")[1]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", action="append", required=True, help="owner/name, repeatable")
    ap.add_argument("--reviewer", required=True, help="GitHub login whose comments form the corpus")
    ap.add_argument("--out", default=Path(__file__).parent / "raw", type=Path)
    ap.add_argument("--force", action="store_true", help="re-download existing files")
    ap.add_argument("--no-reviews", action="store_true", help="skip per-PR review summaries (saves API calls)")
    ap.add_argument("--no-diffs", action="store_true", help="skip compare diffs")
    ap.add_argument("--pulls-pages", type=int, default=1,
                    help="pages of the PR list to fetch (100 PRs each); PRs beyond it are fetched one by one")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    for repo in args.repo:
        s = slug(repo)
        print(f"== {repo}")
        comments = paginate(f"/repos/{repo}/pulls/comments?sort=created&direction=desc", args.out, f"{s}_comments", args.force)
        paginate(f"/repos/{repo}/issues/comments?sort=created&direction=desc", args.out, f"{s}_issue_comments", args.force)
        # The PR list is only an optimisation: any PR missing from it is fetched
        # individually below. Pull objects are large (~17 kB each), so the list is
        # capped at --pulls-pages pages to keep responses small for flaky proxies.
        pulls = paginate(f"/repos/{repo}/pulls?state=all&sort=created&direction=desc", args.out, f"{s}_pulls", args.force,
                         max_pages=args.pulls_pages)
        known = {p["number"] for p in pulls}

        mine = [c for c in comments if c["user"]["login"] == args.reviewer]
        by_pr: dict[int, list] = collections.defaultdict(list)
        for c in mine:
            by_pr[int(c["pull_request_url"].rsplit("/", 1)[1])].append(c)
        print(f"  {len(mine)} inline comments by {args.reviewer} across {len(by_pr)} PRs")

        for n in sorted(by_pr):
            f = args.out / f"{s}_pull_{n}.json"
            if n not in known and (args.force or not f.exists()):
                f.write_text(json.dumps(get(f"{API}/repos/{repo}/pulls/{n}")))
                print(f"  pull #{n} metadata")
            if not args.no_reviews:
                f = args.out / f"{s}_reviews_{n}.json"
                if args.force or not f.exists():
                    f.write_text(json.dumps(get(f"{API}/repos/{repo}/pulls/{n}/reviews?per_page=100")))
                    print(f"  pull #{n} reviews")

        if args.no_diffs:
            continue
        diffs = args.out / "diffs"
        diffs.mkdir(exist_ok=True)
        meta = {}
        pull_meta = {p["number"]: p for p in pulls}
        for n, cl in sorted(by_pr.items()):
            pm = pull_meta.get(n)
            if pm is None:
                f = args.out / f"{s}_pull_{n}.json"
                pm = json.loads(f.read_text()) if f.exists() else None
            if pm is None or "base" not in pm:
                continue
            snap = collections.Counter(c["original_commit_id"] for c in cl).most_common(1)[0][0]
            base = pm["base"]["sha"]
            f = diffs / f"{s}_pr{n}_{snap[:8]}.diff"
            if args.force or not f.exists():
                f.write_bytes(get(f"{WEB}/{repo}/compare/{base}...{snap}.diff", raw=True))
                print(f"  diff PR #{n} @ {snap[:8]} ({f.stat().st_size} bytes)")
            meta[n] = {
                "repo": repo,
                "snapshot_commit": snap,
                "base_sha": base,
                "n_comments_at_snapshot": sum(1 for c in cl if c["original_commit_id"] == snap),
                "n_comments_total": len(cl),
                "title": pm.get("title"),
                "merged": bool(pm.get("merged_at")),
            }
        (diffs / f"{s}_pr_meta.json").write_text(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
