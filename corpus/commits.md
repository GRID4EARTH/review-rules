# What his own commits and merges show

Complement to the review-comment corpus: the *positive* examples. Derived
from `git log origin/main` of healpix-geo (as of ffe6d61, 2026-10) and the
cached PR list (PRs #189 to #303).

## Authorship

| | commits on `main` (no merges) |
|---|---|
| Justus Magin | 132 |
| pre-commit-ci / dependabot | 105 |
| everyone else | 11 |

He wrote 53 % of all commits and essentially all of the hand-written code
between 2025-02-10 and 2026-09-09. Every PR is squash-merged, so one commit
on `main` is one PR. The conventions in his code are therefore the baseline
a reviewer should hold new code to (see "Conventions observed in his code"
below).

## Commit messages

132 subjects: 127 start lowercase, 0 end with a period, 0 use a
`feat:`/`fix:` prefix, median length 26 characters, longest 67. They name
the change, not the motivation: "support compacting cell ids",
"functions to convert between indexing schemes", "back to a dev version",
"ci debugging". Squash merges append `(#N)`. Review consequence: do not
ask for conventional-commit prefixes or long commit messages; he never
commented on commit wording and his own are terse.

## PR descriptions

47 PRs authored by him in the cached list: median body 76 characters, 14
with no body at all, longest 1039 characters. A description exists when
there is a decision to explain, otherwise the title carries it. Review
consequence: a short or empty PR description is not a finding. A long
description is fine but is not a substitute for docstrings and tests.

## What he let through

Among the 16 PRs by other humans in #189 to #303:

- Merged to `main` without any inline comment: #192 (release version bump),
  #297 (emscripten CI job) and #298 (vitest typecheck fix); the latter two
  got one or two conversation comments ("if this looks good to you we can
  merge", "thanks"). All three are small plumbing changes.
- Every other PR to `main` that touched library code or docs received
  inline review: #234 (19 comments), #250 (6), #251 (9), #248 (2), #252 (1).
- #242, #244, #247 show as merged, but into the author's own `integration`
  branch, not `main`; he did not review them (see issue #245 on why).

So the bar is: plumbing and version bumps pass on a one-liner; anything that
adds or changes an API, a test module or a documentation page gets line
comments. The reviewer should behave the same and not generate comments on
release bumps or dependency updates.

## Conventions observed in his code

Read at `origin/main` (ffe6d61). Rule ids refer to `rubric/REVIEW_RUBRIC.md`;
`[NEW]` marks conventions that were turned into rules A10, A11, C8, C9, C10,
D12 and E5 on 2026-10-05.

### Python API

- Every wrapper has the same body: `_check_depth(depth)` → `np.atleast_1d(ipix)`
  → `_check_ipixels(data=ipix, depth=depth)` → `.astype(np.uint64)` →
  `num_threads = np.uint16(num_threads)` → one call into
  `_healpix_geo_python.<scheme>.<same name>` (`healpix-geo-python/python/healpix_geo/nested.py`). [B1, A3]
- Validation helpers live in `healpix_geo/utils.py` (`_check_depth`,
  `_check_ipixels`, `_check_ring`) and have their own tests (`tests/test_utils.py`).
  Where Rust validates (ellipsoid parameters in `EllipsoidLike::into_ellipsoid`),
  Python passes through. [B1, C2]
- Docstring template: one-line summary, `Parameters`, `Returns`, `Raises` (if
  any), `Examples`. The `num_threads` paragraph is byte-identical in 52
  functions; `ellipsoid` always ends with "If the reference ellipsoid is
  spherical, this will return the same result as :py:func:`cdshealpix....`". [A3, D1, D7]
- Examples: `>>> from healpix_geo.nested import X`, `>>> import numpy as np`,
  small literal arrays, result assigned then echoed; doctests run in CI. [D1, D9]
- Dtype contract coerced, not validated: cell ids `uint64`, depth `uint8`,
  coordinates `float64`, neighbour tables `int64` with `-1`. [NEW → A11]
- Options after the geometric inputs are keyword-only:
  `def zone_coverage(bbox, depth, *, ellipsoid="sphere", flat=True)`; all of `auto.py`. [NEW → A10]
- `auto.Grid` is `@dataclass(frozen=True)`; `__post_init__` normalises
  `ellipsoid` through `healpix_geo.ellipsoid.resolve`; dispatch is a dict plus
  `getattr(module, f"to_{to}")`. [A1]
- Lazy imports inside functions to break cycles; `__init__.py` has an explicit
  `__all__` and re-exports Rust classes under stable names. [B5, A1]
- Typing: `from __future__ import annotations` + `TYPE_CHECKING` block; aliases
  (`EllipsoidLike`, `DepthType`) from `Protocol`/`TypedDict` in `typing.py`;
  older functions stay untyped. [B9]

### Python tests

- Zero fixtures in 14 files. Everything is `@pytest.mark.parametrize` with
  `pytest.param(..., id="level0-ring")`, ids dash-joined lowercase. [NEW → C8]
- Class per tested function/object once there are more than two cases
  (`TestZuniq.test_to_nested`, `TestRangeMOCIndex` with 15 methods);
  module-level functions otherwise (`test_auto.py`). [C1]
- Explicit literal expectations for small cases; `cdshealpix` as reference for
  spherical cases (`test_inference.py::TestHealpixToGeographic::test_spherical`). [C4]
- Where no reference exists (ellipsoidal): property assertions
  (`assert np.all(abs(diff_lat) < 0.3)`, `|actual_lat| >= |expected_lat|`, same
  sign) plus a separate `test_ellipsoidal_explicit` with hard-coded values. [C7]
- Error cases are a parametrised `context`:
  `pytest.param(-4, pytest.raises(ValueError, match=r"Depth must be..."), id="depth--4")`
  next to `nullcontext()` (`test_utils.py`, `test_inference.py::test_ellipsoid_like`). [NEW → C9]
- `np.testing.assert_allclose` always with default tolerances; `assert_equal`
  for integers; names `actual`/`expected`; `TODO(keewis):` for known gaps. [NEW → C10]
- Contrast (not his, `test_topology.py`): the same function tested both in a
  class and in module functions, verbose names
  (`test_base_cell_coordinates_to_healpix_rejects_invalid_coordinates`), a
  `for depth in (...)` loop inside a test, `healpy` via `importorskip`.

### Rust

- Three mirrored layers with identical file names: `healpix-geo/src/scalar/nested/coordinates.rs`
  (one cell, `hash: &u64`), `vectorized/nested/coordinates.rs` (`&[u64]` in,
  `Vec<(f64, f64)>` out; body is `with_capacity` + `maybe_parallelize!`),
  `healpix-geo-python/src/indexing_schemes/nested/coordinates.rs` (reshape to
  input shape). `mod.rs` files only list modules. [A3, B2, E4]
- Points are tuples (`&[(f64, f64)]`, `Vec<(f64, f64, f64)>`), unzipped only at
  the PyO3 boundary (`traits::Unzip3`). [A3]
- `maybe_parallelize!(nthreads, iterable, buffer, closure)` with a
  `#[cfg(target_arch = "wasm32")]` serial fallback (`vectorized/execution.rs`);
  the binding crate's variant uses `par_for_each`. [B2]
- `lon.rem_euclid(360.0).to_radians()` and
  `ellipsoid.latitude_geographic_to_authalic(lat.to_radians())` before every
  cdshealpix call. [B8]
- Boundary options are enums: `#[derive(FromPyObject)] enum EllipsoidLike { Named(String), EllipsoidParameters {...}, SphereObject {...} }`
  with `into_ellipsoid() -> PyResult<Ellipsoid>`; hand-written `FromPyObject`
  for `DepthLike` (scalar | `uint8` array). [A5]
- User errors become `PyValueError::new_err(format!(...))` (38 uses) or
  `PyTypeError` (11) in the binding crate; the core crate returns plain values. [B4]
- cdshealpix types used directly: `Layer`, `BMOC`, `RangeMOC`, `MainWind`,
  `Cardinal`; `cdshealpix` pinned to a git rev in the workspace `Cargo.toml`. [A4, A9]
- Doc comments: none in his core-crate code (`///` appears only in files he did
  not write); `index.rs` has 49 `///` lines because pyo3 turns them into Python
  docstrings. [NEW → D12]
- `#[cfg(test)] mod tests` per file, one `#[test]` per case,
  `assert!((x - expected.0).abs() < 1e-8)`; `#[allow(clippy::type_complexity)]`
  on tuple-returning pyfunctions; clippy runs with `-D warnings`. [C6]

### Plumbing

- `pixi.toml` features by concern (`tests`, `dev`, `docs`, `rust`,
  `py311..py314`, `jupyterlite`, `templates`) composed into environments;
  `default = ["tests", "py313", "dev"]`; tasks `tests`, `doctests`, `lint-rust`,
  `rust-tests`, `build-docs` with sphinx `-W`. [B5]
- Runtime deps are only `numpy>=2.0` and `marray`; `shapely` and
  `ragged`/`awkward` are extras; `cdshealpix` is tests-only. [B5]
- `python-ci.yml`: path filters per sub-project, `[skip-ci]` detection,
  3 OS × 3 Python matrix, separate doctests job, every action SHA-pinned with a
  version comment, `persist-credentials: false`, `permissions: contents: read`;
  dependabot grouped weekly. [NEW → E5]
- pre-commit: black, blackdoc, ruff (`F E I UP TID W`,
  `ban-relative-imports = "all"`), prettier, taplo, typos, validate-pyproject,
  action-validator, zizmor, cargo fmt.
- README is badges plus three sentences; CONTRIBUTING requires an issue before
  non-trivial PRs. [D5]

## Contradictions: where his own code falls short of a rule

The rubric applies to new code. These are listed so the reviewer does not
demand fixes to his old code in unrelated PRs, and so the severity of the
rule is calibrated.

- **B1**: `nested.cone_coverage` calls `_check_depth(depth)` and his PyO3
  `cone_coverage` re-checks `depth > 29`
  (`healpix-geo-python/src/indexing_schemes/nested/coverage.rs`). Both his.
  B1 is therefore should-fix, not blocking.
- **B4**: the core crate has `panic!` with `// TODO: return a Result object`
  (`healpix-geo/src/scalar/nested/coverage.rs`) and four
  `// TODO: custom error type` panics (`index/region.rs`); `.unwrap()` in
  `ellipsoid.rs::from_mapping`. The Python layer pre-checks, so the rule now
  reads "errors reachable from Python become exceptions".
- **B8**: his `Raises` docs say `:math:`[0, 4^{29 - depth}[`` (`nested.py`,
  copied from cdshealpix), not `[0, 12·4^depth[`.
- **D1**: 9 of his 22 public functions in `nested.py` lack `Examples` (the five
  coverage functions, `zoom_to`, `siblings`, `angular_distances`,
  `create_empty`). D1 is enforced on new and changed functions only.
- **A3**: `ring.vertices(ipix, depth, ellipsoid, step=1, ...)` and
  `zuniq.healpix_to_lonlat(ipix, ellipsoid, ...)` have no `ellipsoid` default
  while `nested` defaults to `"sphere"`. Match the module being changed.
- **B6**: `nested.to_ring` runs `ipix = np.atleast_1d(ipix)` twice (his).
