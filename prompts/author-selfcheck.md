# Self-check prompt for PR authors (any AI assistant)

If you write code for healpix-geo or xdggs with an AI assistant (Claude,
ChatGPT, Copilot, Cursor, Codex, ...), give it the review rules *before*
you open the pull request. Two ways:

**Automatic (Claude Code, Codex, Cursor and others that read repo
instructions).** The target repository's `CLAUDE.md` / `AGENTS.md` points
at the rubric (see the snippet in the README). Nothing to do; the assistant
reads it when it starts in the repository.

**Manual (any chat).** Attach `rubric/REVIEW_RUBRIC.md` (and `STYLE.md`
if you want the same tone) and paste the block below together with your
diff (`git diff main...HEAD`).

---

The attached REVIEW_RUBRIC.md is the review standard of the GRID4EARTH
projects healpix-geo and xdggs. I am about to open a pull request; the diff
follows. Before I open it:

1. Check the diff against every rule in sections A to E. For each rule I
   violate, quote the offending lines, name the rule id, and propose the
   fix in a suggestion block or a short code snippet.
2. Tell me which rules you could not check from the diff alone (for
   example A3 needs the sibling functions in the same module) so I can
   check them myself.
3. Do not flag formatting (pre-commit handles black, ruff, prettier, cargo
   fmt), missing type hints, or test coverage percentages. The rubric's
   "What he did not comment on" list applies.
4. End with a one-line verdict: ready to open / fix the listed items first
   / split into separate PRs (rule E1), and name the split if so.

Keep the register of the rubric's examples: direct, with the reason, no
praise.
