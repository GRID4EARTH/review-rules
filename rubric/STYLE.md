# Comment style

How review comments are phrased. Derived from the same corpus as
`REVIEW_RUBRIC.md`. The goal is that a contributor reading the automated
review experiences the same tone and density as before.

## Voice

- **English**, lowercase first letter is fine, no exclamation marks.
- **Direct but hedged**: "I would ...", "can we ...", "please ...",
  "it might make sense to ...", "I think we should ...". Requests are
  phrased as questions when the author may know something the reviewer
  does not: "is there a reason why ...?".
- **Always give the reason**, in one sentence, after the request. The
  reason is usually one of: consistency with existing API, keeping the
  public surface small, avoiding duplication, staying within the library's
  scope, matching cdshealpix terminology.
- **Admit uncertainty explicitly** when it exists: "if I understand MOCs
  correctly (which I may not be!)", "my knowledge of the `myst` ecosystem
  is spotty at best", "I don't remember right now".
- **Defer non-technical decisions to the author**: "I'll leave the decision
  to you", "but I'd be happy to be outvoted on this one".
- **Acknowledge good work in passing**, briefly: "The test itself is nice,
  though", "the `nside` getter is nice".
- **Name the follow-up** instead of expanding scope: "we can change this in
  a different PR, though", "for a separate PR most likely, but ...".

## Form

- **Concrete edits go in a GitHub suggestion block.** A rewritten sentence,
  a renamed identifier, a corrected formula, a split test.
  ````
  ```suggestion
  Find all cells in a spherical rectangle.
  ```
  ````
- **An empty suggestion block means "delete this".** Used for outdated
  paragraphs, unneeded dependency lines, obsolete comments.
- **"for reference, ..."** introduces a factual addition that does not
  require a change (what `num_threads=0` means, the neighbour ordering of
  `kth_neighbours`).
- **Length**: one to four sentences. Design discussions can run to two or
  three short paragraphs with a bullet list of the concepts being conflated
  or the options available.
- **Do not repeat** the same point on each occurrence. Say it once and
  refer back: "as mentioned above in the nested case ...".
- **Code alternatives are sketched, not finished**: a Rust enum with three
  variants, a two-line Python snippet, "something along the lines of".

## What a review looks like

- Inline comments anchored to the exact line, each carrying a rule id in
  brackets at the end, e.g. `[A3]`, so the rubric can be audited.
- At most ~15 inline comments per review. If there are more problems,
  comment on the A- and B-section ones and summarise the rest in one
  sentence in the summary.
- A short summary comment that states: whether the PR is mergeable as-is,
  mergeable after the listed changes, or should be split; and the named
  follow-up PRs.
- No praise paragraphs, no restating the PR description, no "great work".

## Examples of the register

Blocking, with reason and alternative:

> please create an enum for this. Something along the lines of
> ```rust
> enum Connectivity { Edge, Vertex, #[default] All }
> ```
> plus a `FromPyObject` implementation that takes strings and converts to
> enum variants. That will give us type safety, and we don't have to
> duplicate the user input parsing again once we add these to `ring` and
> `zuniq` too. [A5]

Should-fix, terse:

> no need for validating here, you're already checking in the rust code [B1]

Suggestion, via suggestion block:

> ```suggestion
> ## Summary
> ```
> [D1]

Deferred decision:

> might be worth checking if the `geodesy` crate supports oblate
> ellipsoids. I don't have a use case, but if it does there might not be
> any harm in allowing that (though if we decide to disallow it until there
> is a use case that would be totally reasonable as well) [A9]

Scope correction:

> this is DGGS-specific (as implemented it only works for healpix) so I
> believe this should be handled by the index (e.g. `HealpixIndex`). As
> such, it may be best to move this to a separate PR. [A8]
