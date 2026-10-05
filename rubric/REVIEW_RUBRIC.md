# Review rubric for healpix-geo and xdggs

This rubric distils the review practice of Justus Magin (`keewis`) on
`grid4earth/healpix-geo` and `xarray-contrib/xdggs`. It was derived from
440 review comments, review summaries and issue comments (2023-11 to
2026-09) and from the code he wrote himself (132 of the 248 commits on
healpix-geo `main`; see `corpus/commits.md` for the conventions observed
there and for the places where his own code falls short of a rule). Each
rule has an id, the rule, the reasoning he gave, and one or more of his own
comments or files as examples.

Use the ids (`A1`, `D3`, ...) when posting a review so that misses and false
positives can be traced back to a rule and the rubric can be corrected.

Companion file: `STYLE.md` describes *how* comments are phrased.

---

## How to prioritise

Justus reviewed in roughly this order of importance. When a PR has many
problems he commented on the top of this list and let the rest wait for a
follow-up PR.

1. **API shape and scope** (section A). These are the comments that block a
   merge. A wrong API is expensive to change later.
2. **Correctness and layering** (section B). Duplicate validation, custom
   parallelism, debug code, dependency hygiene.
3. **Tests** (section C). Structure and what is being tested, not coverage
   numbers.
4. **Documentation** (section D). Terminology, reference-vs-guide
   separation, numpydoc formatting. Many comments, but rarely blocking.
5. **PR hygiene** (section E). One topic per PR, no merge commits from
   integration branches.

What he did **not** comment on, so the reviewer should not either:

- Formatting handled by pre-commit (black, ruff, prettier, cargo fmt,
  taplo, typos). Assume the hooks ran.
- Missing type hints in Python. The codebases do not use them consistently
  and he explicitly deferred that to "a new PR".
- Coverage percentages. He asked for *specific* missing tests, never for a
  number.
- Commit message wording. His own: lowercase, no period, no `feat:`
  prefix, median 26 characters.
- Length of the PR description. His own have a median of 76 characters
  and 14 of 47 are empty; a short description is not a finding.
- Release version bumps, lock-file updates and dependency PRs. He merged
  those on a one-line comment or none; the reviewer should not run on them.

---

## A. API design and scope

### A1. Keep the public namespace minimal

Prefer one function that accepts several input shapes over several
functions. Delete API that has no known user. Scalar and vectorised
variants, if both must exist, need obviously related names.

> "I would like to figure out whether it is possible to join this with
> `cone_coverage` such that there is only one `cone_coverage` function in
> the public namespace." (healpix-geo #252)

> "for reference, the scalar API was added because I thought I'd need this
> for the `gridlook` PR. I personally currently don't have a use-case for
> the JS bindings other than that, so we could delete the scalar API. If we
> do decide to keep it I would prefer the scalar and bulk APIs to have
> similar names: from `healpix_to_lonlat` and `centers` I would not really
> know that they're doing the same thing" (healpix-geo #234)

> "it might actually be better to remove the `from_*` methods (which I also
> don't use in `healpix_geo.auto`)" (healpix-geo #236)

### A2. Return primitive geometric information, not a use-case transform

`healpix-geo` is a geometry library. It returns quantities derived from
geometry (offsets, coordinates, cell ids) and does not act on user data.
If a function returns a recipe for manipulating arrays (swap / flip flags,
numpy-like operations), ask for the underlying quantities instead.

> "Can we change this to return dx and dy? Right now this computes the
> numpy-like operations to transform data, but this makes the API targeted
> to a very specific use-case (and experience tells me that this would be
> very brittle). With dx and dy you should be able to infer all the
> necessary information to compute the transformation yourself."
> (healpix-geo #251)

> "`dx` and `dy` are information computed from geometry, while the
> transform you're proposing is acting on that information. `healpix-geo`
> is a geometry library and does not interact with data at all so far, and
> this would be a significant departure from that boundary." (#251)

### A3. Match the shape of the existing API

New functions follow the conventions of their neighbours: return
`Vec<(u8, u32, u32)>` not three separate `Vec`s, take `&[(u8, u32, u32)]`
not three slices, return a `Vec` instead of writing into a caller-provided
buffer, place scalar code in `crate::scalar::<scheme>` and vectorised code
in `crate::vectorized::<scheme>`. Shared parameter documentation is copied
verbatim from sibling functions.

> "to be consistent with the other API, this should return
> `Vec<(u8, u32, u32)>`." / "this should take a `coords: &[(u8, u32, u32)]`
> to be consistent with the other API (see
> `crate::scalar::nested::coordinates::lonlat_to_healpix` for an example)"
> (healpix-geo #251)

> "can we change this to return a vec instead of receiving a buffer to
> write to? I don't think this is a bottleneck currently, but if it turns
> out that it is (which would need profiling) it would be for the entire
> current API. As such I prefer API consistency for now." (#250)

> "Can you please copy the input docs verbatim from the other functions in
> `nested` for the shared parameters (`ipix`, `depth`, `num_threads`)? I've
> tried to be as consistent as possible." (#250)

### A4. Follow cdshealpix terminology, not healpy

Names and conventions come from `cdshealpix` (Rust) first, then
`astropy-healpix` / `healpy` for cross-library compatibility of *parameter
names* (e.g. `step`). Base-cell coordinates are `(face, i, j)`, not
`(face, x, y)`. Reuse `cdshealpix` types (`MainWind`, `OrdinalSet`) rather
than redefining direction tables.

> "I would follow cdshealpix' naming convention instead of healpy's:
> `(face, i, j)`" (#251)

> "please move this to `crate::scalar::nested` and call it something along
> the lines of `healpix_to_base_cell_coordinates` (to follow cdshealpix
> terminology)" (#251)

> "`cdshealpix` exposes `OrdinalSet::all` and `MainWind::from_index`. Thus,
> you would be able to replace `EDGE_DIRECTIONS` with `OrdinalSet::all()`"
> (#250)

> "I would either stick with `step` for compatibility with `healpy` /
> `cdshealpix` / `astropy-healpix` (despite being written for a different
> domain there is value in keeping the interfaces at least similar)"
> (issue #140)

### A5. Type safety in Rust: enums over strings, private internals

String-valued options crossing the Python/Rust boundary become an `enum`
with a `FromPyObject` implementation, so parsing happens once and is
shared by `nested`, `ring` and `zuniq`. Implementation details (direction
tables) stay private to the crate.

> "please create an enum for this ... That will give us type safety (a
> important thing in rust), and we don't have to duplicate the user input
> parsing again once we add these to `ring` and `zuniq` too (which we will
> have to)." (#250)

> "I wonder if it would be better to keep the directions private to the
> crate? ... We're not planning to support custom directions anyways."
> (#250)

### A6. One way to say it: no redundant parameters, no aliases

Do not accept both `depth` and `nside`. Do not alias parameter names
except as a temporary deprecation step.

> "I think it's fine to ask users to only pass `depth`, and to not accept
> `nside` (not even the `ring` scheme takes the `nside` parameter). That
> should simplify the implementation (and parsing) quite a bit." (#234)

> "I wouldn't alias parameters either, unless it is for the purpose of a
> deprecation cycle (which means the alias is temporary)." (issue #147)

### A7. Backwards compatibility is proportional to maturity

For experimental surfaces (the JS/wasm package, new indexes) a breaking
change is fine and migration guides are noise. For central parameters of
the established Python API (`depth`) a deprecation period of one or two
releases is expected.

> "The `healpix-geo` js package is very new, so I think we can skip the
> backwards compatibility and just do a breaking change." / "probably won't
> need the migration guide, I would consider the package to be very
> experimental at the moment" (#234)

> "`healpix-geo` has existed for more than a year now, and we've kinda
> advertised it as the geoscience healpix package, so I'd be a bit more
> cautious with something as central as the `depth` parameter (but we can
> make the transition period 1-2 releases)." (issue #147)

### A8. Respect the library boundary

`healpix-geo` is purely computational and geometric: no plotting, no I/O,
no xarray. DGGS-specific logic in `xdggs` belongs in the index class, not
in generic conventions code. Point to a separate package when something is
out of scope.

> "I'd rather not have plotting functionality in this library, I'd like it
> to stay a purely geometric library" (issue #132)

> "I don't think `healpix-geo` is the right place for this, it is a purely
> computational library." (issue #200)

> "this is DGGS-specific (as implemented it only works for healpix) so I
> believe this should be handled by the index (e.g. HealpixIndex). As such,
> it may be best to move this to a separate PR." (xdggs #260)

### A9. Reuse upstream and the standard library before reimplementing

If `cdshealpix`, `moc`, `geodesy`, the Rust std, numpy or xarray already
provide it, use that or ask upstream to expose it. Do not add a direct
dependency (e.g. `pandas`) for something a transitive one already gives
you (`xr.indexes.RangeIndex`).

> "`f64` has a `to_degrees` method, so unless we define something that's
> more accurate numerically I think we should use that instead" (#27)

> "`cdshealpix` definitely implements this function, so it might be worth
> asking about making that public instead of reimplementing ourselves
> (since we'd be waiting on `cdshealpix` this can be a separate PR)." (#251)

> "if you use `xr.indexes.RangeIndex` we don't have to list `pandas` as a
> direct dependency" (xdggs #260)

### A10. Options after the geometric inputs are keyword-only

New Python functions take the geometric inputs positionally (`ipix`,
`depth`, `lon`, `lat`, `bbox`, ...) and everything else (`ellipsoid`,
`flat`, `step`, `delta_depth`, `num_threads`) after a `*`. This is uniform
in his coverage functions and in `healpix_geo.auto`, and lets the
positional part grow without breaking callers.

> `def zone_coverage(bbox, depth, *, ellipsoid="sphere", flat=True)`
> (`healpix_geo/nested.py`, his)

Derived from his code, 2026-10-05.

### A11. One dtype contract, coerced in Python, fixed in Rust

Cell ids are `uint64`, depths `uint8`, coordinates `float64`, neighbour
tables `int64` with `-1` for "missing". The Python wrapper coerces
(`np.atleast_1d(...).astype(np.uint64)`, `np.uint16(num_threads)`) and the
Rust signature fixes the type; nobody validates dtypes twice. A new
function that validates dtypes, or returns a different dtype for the same
kind of quantity, breaks the contract.

> every wrapper in `nested.py`: `_check_depth(depth)` →
> `np.atleast_1d(ipix)` → `_check_ipixels(...)` → `.astype(np.uint64)` →
> one call into the Rust module

Derived from his code, 2026-10-05.

---

## B. Implementation

### B1. Validate once, at one layer

If the Rust layer checks an argument, the Python wrapper does not check it
again (and vice versa). Python-side checks live in `healpix_geo/utils.py`
(`_check_depth`, `_check_ipixels`, `_check_ring`) and have their own tests.

> "no need for validating here, you're already checking in the rust code"
> (#250)

Severity: should-fix, not blocking. His own `cone_coverage` checks `depth`
in both layers (`corpus/commits.md`, Contradictions).

### B2. Use `maybe_parallelize!`, never hand-rolled parallelism

All vectorised Rust goes through the shared `maybe_parallelize!` macro
(defined in the core crate's `vectorized/execution.rs` and mirrored in the
Python binding crate's `execution.rs`). Custom rayon pipelines need
profiling evidence first.

> "this is implementing a custom parallelism. I am not convinced this is
> necessary at this stage, so I want this to use the usual
> `maybe_parallelize!` code." (#250)

### B3. No optimisation without profiling

Caller-provided output buffers, custom caching, avoiding allocations: all
of these need a measurement. Suggest the simple version and name the cheap
escape hatch (`functools.lru_cache`, a right shift) if it ever matters.

> "I don't think this is a bottleneck currently, but if it turns out that
> it is (which would need profiling) ..." (#250)

> "Since the results are scalars (mostly `bool`s) and the total number of
> combinations the parameters can have is small (`12 * 8 = 96`), I don't
> think it impacts performance either (and if it does this can easily be
> mitigated using `functools.lru_cache`)" (#251)

### B4. No debug code; errors reachable from Python are exceptions

`assert!` used for debugging is removed before merge; input errors that a
Python caller can trigger become `PyValueError` / `PyTypeError` in the
binding crate (`healpix-geo-python/src`). Code commented out "for later" is
questioned. The core crate still has `panic!` with `// TODO: custom error
type` in places he wrote; do not add more, but do not demand a rewrite of
the existing ones in an unrelated PR.

> "is the `assert!` for debugging purposes? If yes, we should remove that
> before merging, but if not I'd probably return some exception" (#27)

### B5. Dependency hygiene

Heavy or rarely needed packages (`pyproj`, `geopandas`, `lonboard`) are
imported lazily inside the function with a clear `ImportError` message and
kept optional. New entries in `pixi.toml` / `pyproject.toml` must be
justified; transitive dependencies are not listed; install commands that
duplicate the dependency list are removed.

> "if we move this import into the `geodesic_distance` function, we can
> make `pyproj` a optional dependency, which may be desirable to keep the
> number of required dependencies as low as possible." (#134)

> (three empty suggestion blocks deleting `pyproj = "*"` from pixi.toml,
> #137)

> "this will be pulled in by the dependency mechanism, so might not be
> necessary to list separately?" (xdggs #70)

### B6. Remove repetition with the language's idiom

Repeated construction of the same default becomes a `Default` impl; a
repeated helper becomes a method.

> "since this is being repeated multiple times, it might make sense to also
> implement `Default` for the wasm `Ellipsoid` object?" (#234)

### B7. Change the function, don't wrap it

When all callers are in this repository there is no "original" to
preserve. Modify in place rather than adding a checked wrapper around an
unchecked function.

> "is there a reason why we don't just modify `spherical_vertex` directly?
> All of this code is only for js, so no need to preserve the original
> function." (#234)

### B8. Correct normalisation and numeric conventions

Longitudes are normalised with `lon.rem_euclid(360.0).to_radians()` and
latitudes converted with `latitude_geographic_to_authalic` before every
`cdshealpix` call (his pattern throughout `healpix-geo/src`). Index ranges
in new docstrings are `[0, 12 · 4^depth[`; existing docstrings copied the
`cdshealpix` wording, so only flag a range that is actually wrong. Edges of
HEALPix cells are not great circles below level 0.

> "I've been normalizing to `[0, 360]` using rust's `f64::rem_euclid`
> method elsewhere" (issue #165)

> suggestion: ":math:`[0, 12 \cdot 4^{depth}[`." (#134)

### B9. Python typing conventions, when typing is used

Do not annotate `cls`; use `Self` for the return type of classmethods.
Prefer `xr.Index` over the concrete `PandasIndex` in declarations.

> "you don't need to annotate `cls`, or if you do you can annotate it as
> `type[Self]` (and annotate the return type of the class method as `Self`)"
> (xdggs #260)

### B10. Code must be right for the reason it claims

A result that is correct only by coincidence (a transformation that happens
to be a no-op, a filter that never filters, a default that masks a
mismatch) is a defect even when the output is right. Ask "is there a
reason why ...?" and name the condition under which it would break. This
rule covers correctness findings that no other rule names; cite it
together with the closer rule when one exists.

> "I don't really understand what this is doing. To really make the default
> work, we'd need: ..." (xdggs #260)

> "the cells crossing over the dateline now go from slightly more than 180
> to slightly less than 480, so I'm missing a modulo somewhere." (xdggs #67)

Added 2026-10-05 after the first manual run (PR #303): a test built its
PROJ transformer from `EPSG:4326` for every ellipsoid, which only worked
because PROJ's ballpark datum shift was a no-op.

---

## C. Tests

### C1. Group tests per tested function into a class once there are >2

The class name is `Test<FunctionName>`; the function name part is then
dropped from the test method names.

> "please put the test cases into grouped classes if there's more than two
> test functions per tested function. ... that also means we don't need the
> `_face_neighbour_transform_` part in the name of the test functions."
> (#251)

### C2. Test the unit, not the dispatcher

Call the lowest-level public entry point directly (`convention.decode`,
not `xdggs.decode`) so a test does not also exercise routing logic. Have
*some* tests on the low-level API so high-level tests can stay small.

> "these tests should use `convention.decode` instead of going through
> `xdggs.decode` (to avoid testing the dispatching logic as well)" (xdggs
> #260)

> "I do think we need to have *some* tests covering the lower-level API:
> that way, we can have the tests of the higher-level API be less
> extensive (like, one or two tests for each implementation)." (xdggs #28)

### C3. Dummy data in tests signals an API problem

If a test constructs an object only to satisfy a signature and never uses
it, the API probably wants to be a function or a property.

> "the pattern of creating dummy data that is then not used to me
> indicates that there's something wrong with the API" (xdggs #28)

### C4. Explicit expected values for partial cases, reference implementation for full cases

> "for now the test can stay an example test for partial overlaps between
> the dataset and the polygon (i.e. you explicitly construct the expected
> result), and for full overlaps we can compare with `polygon_search`"
> (#27)

### C5. Tests must not reference removed or superseded implementations

Comments comparing with "upstream's `parseEllipsoid`" or asserting that a
removed name is absent from `.d.ts` output are deleted together with the
old implementation.

> "again, no need to compare: I think we should remove `parseEllipsoid`,
> and after that the comments won't make sense anymore. The test itself is
> nice, though" (#234)

### C6. One `#[test]` per behaviour in Rust

Several unrelated assertions in one Rust test function are split into
separate, named tests.

> (suggestion splitting `test_default_sphere` out of a combined test, #234)

### C7. Tests assert properties of this library

A test that only checks the behaviour of a reference implementation
(PROJ, cdshealpix, healpy) or of the test's own setup adds nothing. If it
exists as a sensitivity check for another test, its docstring or a comment
must say so. Conversely, when the inputs for a direct comparison are
already computed, add the comparison; it is free. Where no reference
exists (ellipsoidal results), he asserts properties (bounded difference,
same sign, `|lat_authalic| <= |lat_geographic|`) plus one explicit
hard-coded case.

> "for now the test can stay an example test for partial overlaps ... and
> for full overlaps we can compare with `polygon_search`" (#27)

Added 2026-10-05 after the first manual run (PR #303).

### C8. Parametrize; no fixtures, no loops inside tests

His 14 test modules contain zero fixtures. Cases are
`@pytest.mark.parametrize([...], (pytest.param(..., id="level0-ring"), ...))`
with lowercase dash-joined ids. A `for` loop inside a test body hides which
case failed; a fixture hides the inputs.

> `test_inference.py`, `test_conversion.py` (his) versus a
> `for depth in (...)` loop inside a test in `test_topology.py` (not his)

Derived from his code, 2026-10-05.

### C9. Expected errors are a parametrised `context`

Error cases sit next to the happy path as
`pytest.param(-4, pytest.raises(ValueError, match=r"Depth must be..."), id="depth--4")`
with `nullcontext()` for the valid rows, not as separate `test_*_rejects_*`
functions.

> `tests/test_utils.py`, `test_inference.py::test_ellipsoid_like` (his)

Derived from his code, 2026-10-05.

### C10. Default tolerances, `actual` / `expected`

`np.testing.assert_allclose` is called with default `rtol`/`atol` (zero
explicit tolerances in his tests); `assert_equal` for integer results;
variables are named `actual` and `expected`. An explicit tolerance needs a
comment saying where the number comes from.

> `test_auto.py`, `test_inference.py` (his)

Derived from his code, 2026-10-05.

---

## D. Documentation

### D1. numpydoc formatting and completeness

A blank line precedes every section header. Every new public Python
function has an `Examples` section (`>>> from healpix_geo.nested import X`,
small literal arrays, result assigned then echoed; doctests run in CI).
Math uses `:math:` and exact ranges. Section vocabulary is numpydoc's
(`Parameters`, `Returns`, `Raises`, `See Also`, `Notes`, `Examples`);
"Resume" is "Summary". The shared-parameter paragraphs (`ipix`, `depth`,
`ellipsoid`, `num_threads`) are byte-identical across 52 of his functions;
copy them, do not paraphrase. Enforced on new and changed functions only:
9 of his own 22 public functions in `nested.py` still lack `Examples`.

> "the newline between sections is required" (#134)
> "can you add examples for this?" (#134)
> "these should be part of the examples on the functions" (#128)

### D2. Reference pages list, guides explain

The API reference is a list of functions with their signatures (never
`:nosignatures:`). Explanatory prose ("which module should I use") moves to
the user guide. Code snippets illustrating a function belong in that
function's docstring.

> "this is a reference page (i.e. a list of available functions), could we
> move this to a user guide?" / "The signature is actually important" (#128)

### D3. Terminology is precise

- "indexing scheme", not "coordinate system", for nested / ring / zuniq.
- "nested" and "ring" are English words: lowercase, never `NESTED`.
- A MOC (variable cell sizes) is distinct from the MOC-based index, which
  is an implementation detail.
- `box_coverage` finds cells in a "spherical rectangle", not a "box
  coverage" or "spherical angle".
- "ellipsoid of revolution" when triaxial ellipsoids must be excluded.
- The authalic sphere has the same surface area as the ellipsoid; cells
  are on that sphere and mapped back.
- Cell edges are only great circles at level 0.
- The Rust doc of a function inside `nested` does not repeat "nested".

> "I would make this chapter about healpix' 'indexing schemes': while not
> technically wrong, 'coordinate systems' are usually associated with more
> direct ways of referring to positions in space." (#128)

> "Spelling the indexing scheme all-caps has always felt weird to me since
> 'nested' is a proper english word and not an abbreviation." (#251)

> "This paragraph collapses multiple things under the term MOC" (#128)

### D4. Claims match what is implemented

Don't frame a list as "HEALPix in general" if it only lists what
`healpix-geo` supports; don't describe a point-to-both-schemes conversion
as a nested-to-ring conversion; don't describe assigning coordinates as
"resampling".

> "there are a lot more than three schemes, but these are the only ones
> `healpix-geo` supports. If we frame this as 'HEALPix in general', then
> we'd also have to at least include `nuniq`." (#128)

> "this doesn't exactly convert between `nested` and `ring` (it converts a
> point to both schemes)." (#128)

### D5. Delete rather than defer

Placeholder pages, outdated paragraphs, migration guides for experimental
packages, release timelines, duplicated dependency lists, and
"this project ..." filler sentences are removed. An empty suggestion block
is the usual form.

> "probably should remove / hide this until we actually have content here"
> (#128)

> "I don't think we should mention release timelines at all, that just
> sets the wrong expectations" (xdggs #70)

> "this part is outdated now ... Instead, we should credit the `geodesy`
> and `moc` crates" (#248)

### D6. Structure follows the reader

The recommended entry point (`Grid`, `healpix_geo.auto`) comes first;
other APIs are "advanced" later. Overview pages point to detailed
chapters. Function tables group by what the function consumes (geometry
in, cells out) rather than by shape.

> "if we recommend `Grid` as the entrypoint I would argue this should be
> what a reader sees first, and frame the other API as advanced in a later
> section (if at all)." (#234)

> "Can you move `box_coverage`, `elliptical_cone_coverage` and
> `polygon_coverage` into the section above, together with `zone_coverage`
> and `cone_coverage`? All of these take some sort of geometry that is
> then approximated by cell ids." (#137)

### D7. Links and credits

Cross-references use MyST referencing syntax (labels), not relative
markdown links under a "See Also" heading. Upstream crates are credited
accurately (`cds-healpix-rust`, `moc`, `geodesy`). Funding acknowledgements
list the actual grants.

> "I'd change this to use `myst`'s referencing syntax somewhere in the
> previous sections (like hyperlinks)." (#45)

### D8. Rust doc comments describe the crate, not the repository

Triple-slash docs reference items by crate path
(`healpix_geo_wasm::ring`), never by source file path (`js/src/ring.rs`).

> "if this is intended for rust documentation ... it might be better to not
> reference the source paths and instead talk about
> `healpix_geo_wasm::ring`." (#234)

### D9. Examples use their results

A call whose return value is discarded reads like an in-place operation.
Assign and use it, or remove the line.

> "the result of this operation is immediately discarded. Since this can be
> misunderstood as an inplace operation, can we either remove this or
> assign the result to a variable and make use of it?" (xdggs #70)

### D10. Don't lecture outside the library's competence

Advice on which reference ellipsoid to use is kept to one sentence
("WGS84 for accuracy, `sphere` for low-accuracy use"), not a geodesy
tutorial.

> "We're probably not in the best place to talk about the differences
> between the different ellipsoids, so I'd probably try avoid that."
> (#128)

### D11. English, and no typos in prose

Captions and headings are in English (`caption: User guide`). Obvious
typos get a suggestion block.

### D12. Rust `///` docs where they become Python docstrings

`#[pyclass]` and `#[pymethods]` items in the binding crate carry `///`
docs (pyo3 turns them into Python docstrings; his `index.rs` has 49 such
lines). In the core crate he wrote no `///` docs at all, so their absence
there is not a finding, and when present they follow D8.

Derived from his code, 2026-10-05.

---

## E. PR hygiene

### E1. One topic per PR, branched from `main`

Mixed PRs (docs plus a new function) are split. Merge commits that pull in
an integration branch are reverted. A 1.5k-line multi-topic PR is closed,
not reviewed.

> "it looks like there's a mix-up between this PR and #134. I think it
> might be better to cleanly separate between the two, such that this only
> does documentation changes, and #134 takes care of everything related to
> the distance function (code, tests, documentation)." (#137)

> "this kind of workflow makes it almost impossible to reasonably review
> PRs (the PR you proposed has 1.5k changed lines on different topics)."
> (issue #245)

### E2. Name the follow-up explicitly

Anything out of scope is called out as "separate PR" with what it would
contain, instead of being silently expanded or silently dropped.

> "Additionally, `cdshealpix` definitely implements this function ... since
> we'd be waiting on `cdshealpix` this can be a separate PR." (#251)

### E3. Merge pragmatically

When the remaining issues are small, say so and merge with named
follow-ups. Unrelated CI failures are stated as unrelated.

> "thanks, this is close enough that I think we can merge this now and
> follow up with some other PRs." (#234)

### E4. Package layout

Python code lives in an importable package directory (`healpix_geo`, not
`healpix-geo`). Rust is three mirrored layers with identical file names:
`healpix-geo/src/scalar/<scheme>/<topic>.rs` (one cell), `vectorized/<scheme>/<topic>.rs`
(`&[T]` in, `Vec<T>` out, body is `with_capacity` + `maybe_parallelize!`),
`healpix-geo-python/src/indexing_schemes/<scheme>/<topic>.rs` (reshape to the
input shape). `mod.rs` files only list modules.

### E5. Workflow hygiene

GitHub Actions are SHA-pinned with a version comment, checkouts use
`persist-credentials: false`, jobs declare minimal `permissions`, triggers
are path-filtered per sub-project, dependabot updates are grouped. zizmor
and action-validator run in pre-commit; a workflow change that fails them
is not mergeable.

> `.github/workflows/python-ci.yml`, `.github/dependabot.yml` (his)

Derived from his code, 2026-10-05.

---

## Severity labels used in reviews

- **blocking**: A-section violations, B2, E1, E5. Must be fixed or
  explicitly deferred with a named follow-up PR before merging.
- **should-fix**: remaining B and C rules (B1, B10, C7 through C10
  included), D1 formatting, D3 terminology, D12.
- **suggestion**: D5 through D11, B6, C6. Usually a one-line suggestion
  block.

When a rule and his own existing code disagree (list in
`corpus/commits.md`, "Contradictions"), hold *new* code to the rule and do
not ask the PR to fix his old code unless the PR touches those lines.
