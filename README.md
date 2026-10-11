# GRID4EARTH review agent

Automated pull-request review for `healpix-geo` and `xdggs` that reproduces
the review practice of the project's former maintainer. The knowledge lives
in two Markdown files (`rubric/`); everything else is plumbing to apply,
test and deploy them.

This directory is self-contained and meant to become its own repository
(for example `GRID4EARTH/review-rules`). Target repositories then need only
a short caller workflow, and anyone, human or AI, can be pointed at the
rubric.

```
rubric/REVIEW_RUBRIC.md      what to flag: 48 rules in 5 sections, each with his own comments or code as examples
rubric/STYLE.md              how to phrase it: tone, suggestion blocks, length, summary format
prompts/review-prompt.md     paste-ready prompt to review a PR in any AI chat
prompts/author-selfcheck.md  paste-ready prompt for PR authors to check their own diff
.claude/agents/              Claude Code subagent definition (grid4earth-reviewer)
.github/workflows/           reusable workflow (Bedrock, workflow_call only)
templates/                   caller workflow to copy into target repos
corpus/                      his 440 review comments (raw API pages, JSONL, readable Markdown, stats) and
                             commits.md: what his own 132 commits, PR descriptions and silent merges show
eval/                        offline test: cases from 18 past PRs, a one-call reviewer, a comparison report,
                             and eval/manual/ with the manual runs (first one: PR #303)
static-checks/               deterministic subset of the rubric for pre-commit / CI
```

---

## How to use it, by situation

### 1. Someone opened a PR and you review it in Claude Code (no AWS needed)

This is the manual mode. It needs the healpix-geo (or xdggs) checkout, this
directory, and Claude Code. Nothing is posted to GitHub unless you paste it.

One-time, in the target repository checkout:

```bash
mkdir -p .claude/agents && cp review-agent/.claude/agents/grid4earth-reviewer.md .claude/agents/
```

(If this directory lives elsewhere, adjust the source path. The agent looks
for the rules in `.review-rules/`, `review-agent/`, `../review-rules/`, or
in `$REVIEW_RULES_DIR`.)

Per PR, in Claude Code opened on the target repository:

1. Make sure the checkout can see the PR. Any PR, including one from a
   fork, is reachable by its pull ref; `gh` is not required:
   ```bash
   git fetch origin pull/303/head:pr-303 && git fetch origin main
   ```
2. Ask Claude Code:
   > use the grid4earth-reviewer agent to review PR 303 (branch pr-303 against origin/main)
3. Read the result. It is printed as Markdown (summary, one block per
   comment with rule id and severity, reviewer notes) and saved to
   `review-agent/eval/manual/pr303_review.md`.
4. Decide what to post. Copy the comments you agree with into the PR as
   line comments and the summary as the review body. Drop the ones you
   disagree with, and if a dropped one points at a rubric problem, fix
   the rubric (section 7).

What the agent does, so you can judge its output: reads the rubric, style
guide and `corpus/commits.md`; diffs the PR against the current
`origin/main`; reads the sibling functions and tests at the PR head for
the rules that need context (A3, B1, B2, C1); comments at most 15 times;
never runs code; never posts.

Time per PR: a few minutes of model time for a 100-to-500-line diff. The
first manual run (PR #303, 138 lines) produced three comments and is kept
verbatim in `eval/manual/pr303_review.md` as a reference for what to
expect.

### 2. Review a PR in a chat window instead (claude.ai, ChatGPT, ...)

Use `prompts/review-prompt.md`. Attach `rubric/STYLE.md` and
`rubric/REVIEW_RUBRIC.md`, paste the PR description and the diff
(`https://github.com/<owner>/<repo>/pull/<N>.diff`), then paste the prompt
block. The output shape is the same as in Claude Code. The chat model
cannot read sibling files, so it will say "cannot check from the diff"
for rules A3 and B1; check those two yourself.

In claude.ai, a Project with the two rubric files as knowledge saves the
attaching step.

### 3. PR authors: tell your AI to follow the rules before opening the PR

Yes, contributors can and should. Two mechanisms:

**Automatic for assistants that read repository instructions** (Claude
Code, Codex, Cursor, Copilot agents): add a pointer in the target
repository's `CLAUDE.md` or `AGENTS.md`. Suggested text for healpix-geo:

```markdown
## Review standard

Pull requests are reviewed against the GRID4EARTH review rubric:
https://github.com/GRID4EARTH/review-rules/blob/main/rubric/REVIEW_RUBRIC.md
Before proposing or opening a PR, check the diff against sections A to E
of that file and fix what it flags. Rule ids (A3, C8, ...) are how review
comments refer to it.
```

**Manual for any chat assistant**: `prompts/author-selfcheck.md`. The
author attaches `REVIEW_RUBRIC.md`, pastes `git diff main...HEAD` and the
prompt, and gets a rule-by-rule check plus a "ready / fix first / split"
verdict.

Suggested paragraph for `CONTRIBUTING.md` of the target repositories:

```markdown
### Review standard

Reviews follow the rubric in GRID4EARTH/review-rules. If you write code
with an AI assistant, give it `rubric/REVIEW_RUBRIC.md` from that
repository before you open the pull request (see `prompts/author-selfcheck.md`
there). Review comments cite rule ids such as `[A3]`; the rubric explains
each one with examples.
```

### 4. Test the rubric offline, against his real reviews (needs Bedrock or an API key)

`eval/run_review.py` sends the rubric plus one past PR diff to the model in
a single call and writes the findings as JSON. No agent loop, no
repository checkout, no GitHub. `eval/compare.py` then puts the model's
findings next to the comments he actually left on that PR.

```bash
cd review-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt              # Python 3.10+

# see the exact prompt for one PR without calling anything
python eval/run_review.py --case eval/cases/healpix-geo_pr251.json --dry-run

# one PR on Bedrock (uses your AWS credential chain: aws sso login, profile, env vars)
python eval/run_review.py --case eval/cases/healpix-geo_pr251.json --region eu-west-3

# all 18 PRs, then the side-by-side report
python eval/run_review.py --all --region eu-west-3
python eval/compare.py && open eval/results/report.md
```

Defaults: provider `bedrock`, model `anthropic.claude-opus-5-5`, effort
`high`. Override with `--model`, `--provider anthropic` (first-party API,
`ANTHROPIC_API_KEY`), `--effort`. The rubric is sent as a cached system
prompt, so the 18 runs share one cache write. Each PR is roughly 10k to
20k input tokens.

How to read the report: a row where both cells make the same point is a
hit. A row with a finding at the same location but a different point is a
miss. A finding with nothing nearby is either a false positive or
something he let slide; decide per row. Then edit the rubric and re-run
with `--force`. Stop when the misses are things no diff-only reviewer
could know.

The cases use the diff **as it was when he reviewed**, not the merged
version. Cases: healpix-geo PRs 27, 45, 128, 134, 137, 234, 248, 250, 251
(58 ground-truth comments) and xdggs PRs 20, 28, 39, 67, 70, 88, 95, 151,
260 (47). PRs with a single comment were skipped.

### 5. Deterministic checks, no model at all

```bash
python static-checks/check_rubric_static.py --changed                      # files changed vs. main
python static-checks/check_rubric_static.py healpix-geo-python/ healpix-geo/  # or explicit paths
```

Covers D3 (all-caps scheme names), D1 (numpydoc blank lines, missing
Examples), C1 (ungrouped tests), B2 (rayon outside `maybe_parallelize!`),
B1 (duplicate Python-side validation, reported as "check"), D5
(placeholder pages), D8 (source paths in Rust docs), A9 (hand-written
angle conversion), D11 (non-English captions). On the current healpix-geo
tree it reports 26 findings, all "public function without Examples" on
functions he merged himself with "we'll need examples at some point". Use
`--changed` and treat it as advisory, or drop that check.

### 6. Later: run it in CI on Amazon Bedrock

The reusable workflow `.github/workflows/review-reusable.yml` runs
`anthropics/claude-code-action@v1` with `use_bedrock: "true"`. Inference is
billed to an AWS account; no Anthropic API key exists anywhere. The caller
template is `templates/caller-rubric-review.yml`.

What a deployment needs, in general terms (the prerequisites are also listed
at the top of the reusable workflow):

1. **AWS.** An IAM role that GitHub Actions can assume through OIDC, limited
   to Bedrock inference, and the chosen Claude model enabled in the region.
2. **GitHub App.** A custom GitHub App (webhooks off; Contents, Issues,
   Pull requests: read and write) installed on the target repositories. The
   Anthropic-hosted Claude GitHub App cannot be used with Bedrock.
3. **Secrets.** The three secrets the reusable workflow declares, in the
   caller's repository or organisation.
4. **Target repository.** Copy `templates/caller-rubric-review.yml` to
   `.github/workflows/rubric-review.yml`, fill in the `CHANGE-ME` values,
   merge to the default branch.

Which account, region, App and repositories GRID4EARTH uses, who administers
them and what it costs are not in this public repository; they are
documented for members in the private `project-guidelines` repository
(`docs/review-automation.md`).

Behaviour of the caller:

- Pull requests from branches **inside** the repository are reviewed
  automatically on open and on every push. Bot PRs (dependabot,
  pre-commit.ci) and release bumps are skipped; he never reviewed those
  line by line.
- Pull requests **from forks** cannot receive secrets or OIDC tokens on
  `pull_request` events (GitHub rule). A maintainer triggers the review by
  commenting `@claude review`; only OWNER / MEMBER / COLLABORATOR comments
  count. `pull_request_target` would avoid the comment but runs with write
  permissions on untrusted code, so it is not used.
- The review is advisory. Nothing blocks merging. Keep it that way until the
  eval report (section 4) shows the rubric is trusted.

Two things the subagent that researched the action reported but that were
not verified here: WebSearch is unavailable on Bedrock (irrelevant for
reviews), and reusable workflows with Bedrock had a 403 regression in some
action versions. If the reusable form fails with 403, paste the steps of
`review-reusable.yml` directly into the caller as a fallback.

### 7. Keep the rubric alive

- Every automated comment ends with a rule id. When a comment is wrong,
  find the rule and fix the rule, not the comment.
- When a human reviewer makes a point the rubric lacks, add it with the
  comment as the example. That is how this file was built; B10 and C7 were
  added after the first manual run.
- Each manual run is saved under `eval/manual/`. Re-run the offline eval
  (section 4) after each rubric change; the report is the regression test.

### 8. Refresh the corpus

```bash
# authenticated: 5000 requests/hour. Either set GITHUB_TOKEN, or have `gh auth login` done;
# the script picks up `gh auth token` by itself (GH_BIN=/path/to/gh if gh is not on PATH).
python corpus/fetch_corpus.py --repo GRID4EARTH/healpix-geo --repo xarray-contrib/xdggs --reviewer keewis
python corpus/build_corpus.py
python eval/build_cases.py
```

The fetcher is resumable and skips files that already exist. `corpus/raw/`
holds, for both repositories: all inline review comments, all
PR-conversation and issue comments, his review-summary bodies, PR
metadata, and the reviewed-commit diff of every PR he commented on. It
retries truncated responses and falls back to `curl` for proxies that cut
large responses.

---

## Sources, and what each one contributed

- **Review comments** (440, both repositories): the rules themselves, the
  reasoning, the register. Sections A to E of the rubric.
- **His own code** (132 commits, 53 % of healpix-geo `main`): the positive
  examples and seven conventions he enforced by example rather than by
  comment (A10, A11, C8, C9, C10, D12, E5), plus six places where his
  code falls short of a rule, which calibrated severities. `corpus/commits.md`.
- **Silent merges**: which PRs he let through without line comments
  (release bumps, CI fixes), which is why the caller workflow skips bot and
  release PRs.
- **Commit messages and PR descriptions**: terse by habit, so the reviewer
  does not comment on either.

## Limits

The rubric reproduces the *form* of his judgement and the *facts* he
stated (cdshealpix terminology, the geometry-library boundary, the
`maybe_parallelize!` rule). It cannot reproduce judgement that depended on
knowledge he never wrote down. Expect the agent to be strongest on sections
B, C, D and weakest on "this API will be brittle" calls in section A. Have
him review the rubric before he leaves; that is the cheapest improvement
available.
