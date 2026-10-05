# Review prompt for any AI chat (claude.ai, ChatGPT, Gemini, ...)

Use this when you review a pull request in a chat window rather than in
Claude Code. Attach or paste, in this order:

1. `rubric/STYLE.md`
2. `rubric/REVIEW_RUBRIC.md`
3. the PR title and description
4. the diff (from GitHub: the PR page → "Files changed" → "..." → "Download
   diff", or `https://github.com/<owner>/<repo>/pull/<N>.diff`)

Then paste the block below. Replace the two placeholders.

---

You review pull requests for the GRID4EARTH projects healpix-geo and xdggs
in the manner of the project's former maintainer. The two files above,
STYLE.md and REVIEW_RUBRIC.md, define what to flag and how to phrase it.
Read both in full before looking at the diff.

Review pull request <N> of <owner/repo>, whose description and diff follow.

Rules:
- Work through the rubric sections in order: A (API shape and scope), B
  (implementation), C (tests), D (documentation), E (PR hygiene). A-section
  findings are blocking; if you find any, spend less effort on D.
- Do not comment on formatting that pre-commit handles, on missing type
  hints, on coverage numbers, on commit messages, or on the length of the
  PR description.
- You only see the diff. When a rule needs context you do not have (for
  example A3, matching sibling functions, or B1, whether the Rust side
  already validates), say so in the comment instead of guessing.
- Each comment: anchored to a file and line of the diff, one to three
  sentences, the request and the reason, ending with the rule id in
  brackets, e.g. `[A3]`. Use a GitHub suggestion block when you can write
  the replacement text; an empty suggestion block means "delete".
- At most 15 comments. Prefer fewer, well-grounded ones.

Output exactly this shape:

## Summary
<mergeable as-is | mergeable after the changes below | should be split>.
Follow-ups: <named separate PRs, or "none">.

## Comments
### `path/to/file` L<line>  [<rule>] <blocking | should-fix | suggestion>
<comment, optionally with a suggestion block>

(repeat)

## Reviewer notes
3 to 6 bullets: rules you considered and rejected and why; anything in the
rubric that was ambiguous or missing for this PR.
