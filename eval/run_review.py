#!/usr/bin/env python3
"""Run the rubric reviewer *statically*: one model call per PR, no agent,
no GitHub Action, no repository checkout.

The model receives the style guide and rubric as a cached system prompt and
the PR diff as the user message, and returns a JSON list of findings. Use
this to tune the rubric against past PRs before enabling the CI workflow.

Providers
---------
* ``--provider bedrock`` (default): Amazon Bedrock via the ``AnthropicBedrockMantle``
  client. Uses your normal AWS credential chain (``aws sso login``, env vars,
  profile). Model ids carry the ``anthropic.`` prefix, e.g.
  ``anthropic.claude-opus-5-5``.
* ``--provider anthropic``: first-party API, ``ANTHROPIC_API_KEY`` or ``ant auth login``.

Install: ``pip install -r requirements.txt`` (Python 3.10+).

Examples
--------
    # print the prompt for one case, no API call
    python eval/run_review.py --case eval/cases/healpix-geo_pr251.json --dry-run

    # review one PR on Bedrock in eu-west-3
    python eval/run_review.py --case eval/cases/healpix-geo_pr251.json --region eu-west-3

    # review every case and write eval/results/*.json
    python eval/run_review.py --all
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUBRIC = ROOT / "rubric" / "REVIEW_RUBRIC.md"
STYLE = ROOT / "rubric" / "STYLE.md"

OUTPUT_SPEC = """
Return ONLY a JSON object, no prose before or after, with this shape:

{
  "verdict": "mergeable" | "mergeable after changes" | "should be split",
  "summary": "<one or two sentences>",
  "follow_ups": ["<named separate PR>", ...],
  "findings": [
    {
      "path": "<file path exactly as in the diff>",
      "line": <integer line number in the NEW file, from the hunk headers>,
      "rule_ids": ["A3", ...],
      "severity": "blocking" | "should-fix" | "suggestion",
      "comment": "<the review comment, in the register of STYLE.md, ending with the rule id in brackets>"
    }
  ]
}

At most 15 findings. Prefer fewer, well-grounded findings. Do not comment on
anything pre-commit handles, on missing type hints, or on coverage numbers.
"""

MAX_DIFF_CHARS = 350_000  # ~90k tokens; well inside the context window


def build_system() -> list:
    text = (
        "You review pull requests for the GRID4EARTH projects healpix-geo and xdggs "
        "in the manner of the project's former maintainer.\n\n"
        "# STYLE.md\n\n" + STYLE.read_text() + "\n\n# REVIEW_RUBRIC.md\n\n" + RUBRIC.read_text()
    )
    # One cache breakpoint on the rubric: every case re-uses it.
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


def build_user(case: dict) -> str:
    diff = case["diff"]
    note = ""
    if len(diff) > MAX_DIFF_CHARS:
        diff = diff[:MAX_DIFF_CHARS]
        note = f"\n\n[diff truncated to {MAX_DIFF_CHARS} characters]"
    return (
        f"Repository: {case['repo']}\nPull request #{case['pr']}: {case['title']}\n\n"
        f"## Description\n\n{(case.get('body') or '(none)').strip()}\n\n"
        f"## Diff (base {case['base_sha'][:8]} ... head {case['snapshot_commit'][:8]})\n\n"
        f"```diff\n{diff}\n```{note}\n\n"
        "Review this diff against the rubric. You cannot open other files, so when a rule "
        "needs context you do not have (for example A3, matching sibling functions), say so "
        "in the comment instead of guessing.\n" + OUTPUT_SPEC
    )


def make_client(provider: str, region: str | None):
    import anthropic

    if provider == "bedrock":
        return anthropic.AnthropicBedrockMantle(aws_region=region or "eu-west-3")
    return anthropic.Anthropic()


def default_model(provider: str) -> str:
    return "anthropic.claude-opus-5-5" if provider == "bedrock" else "claude-opus-5-5"


def extract_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if m:
        text = m.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in model output")
    return json.loads(text[start:end + 1])


def review(client, model: str, effort: str, case: dict, system: list) -> dict:
    import anthropic

    user = build_user(case)
    t0 = time.time()
    with client.messages.stream(
        model=model,
        max_tokens=16000,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"effort": effort},
    ) as stream:
        msg = stream.get_final_message()
    elapsed = time.time() - t0

    if msg.stop_reason == "refusal":
        raise RuntimeError(f"model refused: {getattr(msg, 'stop_details', None)}")
    text = "".join(b.text for b in msg.content if b.type == "text")
    try:
        parsed = extract_json(text)
    except (ValueError, json.JSONDecodeError) as e:
        parsed = {"parse_error": str(e), "raw": text, "findings": []}
    usage = msg.usage
    return {
        "case": case["id"],
        "model": msg.model,
        "effort": effort,
        "elapsed_s": round(elapsed, 1),
        "usage": {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", None),
            "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", None),
        },
        **parsed,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--case", type=Path, action="append", help="case JSON file (repeatable)")
    g.add_argument("--all", action="store_true", help="every file in eval/cases/")
    ap.add_argument("--provider", choices=["bedrock", "anthropic"], default="bedrock")
    ap.add_argument("--model", help="override the model id")
    ap.add_argument("--region", help="AWS region for Bedrock (default eu-west-3)")
    ap.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"], default="high")
    ap.add_argument("--out", type=Path, default=ROOT / "eval" / "results")
    ap.add_argument("--dry-run", action="store_true", help="print the prompt and exit without calling the API")
    ap.add_argument("--force", action="store_true", help="re-run cases that already have a result")
    args = ap.parse_args()

    cases = sorted((ROOT / "eval" / "cases").glob("*.json")) if args.all else args.case
    system = build_system()

    if args.dry_run:
        for cf in cases:
            case = json.loads(cf.read_text())
            user = build_user(case)
            print(f"=== {case['id']}: system {len(system[0]['text']):,} chars, user {len(user):,} chars "
                  f"(~{(len(system[0]['text']) + len(user)) // 4:,} tokens)")
            print(user[:3000] + ("\n[...]" if len(user) > 3000 else ""))
        return

    try:
        import anthropic  # noqa: F401
    except ImportError:
        sys.exit("pip install -r review-agent/requirements.txt (needs Python 3.10+)")

    client = make_client(args.provider, args.region)
    model = args.model or default_model(args.provider)
    args.out.mkdir(parents=True, exist_ok=True)

    for cf in cases:
        case = json.loads(cf.read_text())
        rf = args.out / f"{case['id']}.json"
        if rf.exists() and not args.force:
            print(f"skip {case['id']} (result exists; --force to redo)")
            continue
        print(f"reviewing {case['id']} with {model} (effort={args.effort}) ...", flush=True)
        try:
            result = review(client, model, args.effort, case, system)
        except Exception as e:  # report and continue with the next case
            print(f"  FAILED: {type(e).__name__}: {e}")
            continue
        rf.write_text(json.dumps(result, indent=1, ensure_ascii=False))
        u = result["usage"]
        print(f"  {len(result.get('findings', []))} findings, verdict: {result.get('verdict')}, "
              f"{result['elapsed_s']}s, in={u['input_tokens']} cached={u['cache_read_input_tokens']} out={u['output_tokens']}")


if __name__ == "__main__":
    main()
