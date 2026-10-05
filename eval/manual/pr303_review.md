# Manual run of grid4earth-reviewer on PR #303 (2026-10-05)

Run as a Claude Code subagent with the agent definition, rubric and style
guide, the PR diff, and read access to the repository at the PR base
(`ffe6d61`). No network, no code executed. Verbatim output follows.

---

## Summary
mergeable after the changes below. The PR is one topic (consistency tests against PROJ plus the matching test dependency), and `healpix-geo-python/python/healpix_geo/tests/` is the layout on `main` at `ffe6d61`, so the branch is based on current `main`. `pyproj = "*"` sits in the `tests` pixi feature next to `cdshealpix` / `shapely`, which is the right place, and the module-level `importorskip` keeps it optional. The two should-fix comments are about how PROJ is set up (source CRS) and one cheap assertion whose inputs are already computed but never checked; the rest is a suggestion.

for reference, the new tests take care of two of the `TODO(keewis)` lines at the top of `test_inference.py` ("explicit tests for vertices", "maybe double check ellipsoidal lon / lat using pyproj?"), so those could be removed in this PR (not part of the diff, so no inline comment).

Follow-ups: a short note in the user guide (e.g. `user-guide/ellipsoids.md`) that `+proj=healpix` with the parameters from `ellipsoid.resolve` is the CRS to use for healpix-geo data; that is the motivation given in the PR description and the docs currently do not mention PROJ or a CRS anywhere (separate PR).

## Comments

### `healpix-geo-python/python/healpix_geo/tests/test_proj.py` L42  [B8] should-fix
is there a reason to start from `EPSG:4326` rather than from the healpix CRS' own geographic CRS? For `unitsphere`, `sphere` and `GRS80` the source datum (WGS84) does not match the target ellipsoid, so PROJ inserts a "ballpark" geographic offset between the two, and the test only works because that offset happens to be a no-op (and because pyproj allows ballpark operations by default). With `crs.geodetic_crs` the transformation is just the projection on the ellipsoid we asked for, which is what the module docstring describes. The same applies to the inverse transformer on L130; with the change below that one can reuse this transformer with `direction="INVERSE"`.
```suggestion
    transformer = pyproj.Transformer.from_crs(crs.geodetic_crs, crs, always_xy=True)
```
[B8]

### `healpix-geo-python/python/healpix_geo/tests/test_proj.py` L35  [B6] suggestion
`crs` is derived from `(ellipsoid, lon_0)` at every call site, so both end up being passed twice (e.g. `project_cells(proj_healpix("WGS84", 45.0), ipix, depth, "WGS84", 45.0)` on L84). It might make sense to build the CRS inside and return the transformer instead, something along the lines of
```python
def project_cells(ipix, depth, ellipsoid, lon_0=0.0):
    crs = proj_healpix(ellipsoid, lon_0)
    transformer = pyproj.Transformer.from_crs(crs.geodetic_crs, crs, always_xy=True)
    ...
    return transformer, x, y, cx, cy, width
```
which removes the duplicated arguments and gives `test_inverse_projection` the inverse for free. I'll leave the exact shape to you. [B6]

### `healpix-geo-python/python/healpix_geo/tests/test_proj.py` L67  [C4] should-fix
`project_cells` already computes the PROJ image of the `healpix_to_lonlat` centres (`cx`, `cy`), but none of the tests looks at them. Can we assert that they coincide with the centre of the square? Something like
```python
x, y, cx, cy, width = project_cells(...)
side = width / 4 / 2**depth
np.testing.assert_allclose(cx, x.mean(axis=1), atol=RTOL * side)
np.testing.assert_allclose(cy, y.mean(axis=1), atol=RTOL * side)
```
(`atol` rather than `rtol`, since cells on the `x = 0` column and on the equator have `cx == 0` / `cy == 0`). That would be the one direct comparison of `healpix_to_lonlat` against PROJ in this module (the other tests cover `vertices` and `lonlat_to_healpix`), and it is essentially free since everything is already computed. The nudge does not get in the way: shrinking the vertices symmetrically towards the centre leaves their mean in place to first order. [C4]

## Reviewer notes
- A1–A9 do not apply: no public API changes, only tests and a test-only dependency. A8 was considered for `test_cells_are_not_squares_for_other_lon_0` (L80), which asserts a property of PROJ's `lon_0=45°` layout rather than of healpix-geo (it is a sensitivity check for the square test). The rubric has no rule for "the test checks the reference library, not ours", and A8 is about library code, so I left it as a note; the author may want to say in the comment that it guards the test above, or drop it.
- E1 (branch based on outdated `main`): checked and rejected. `git ls-tree ffe6d61` shows `healpix-geo-python/` and no `python/` directory, so the PR path matches `main`; the local working tree is simply on an older branch (`871201d`, layout `python/healpix-geo/`). All sibling files were read via `git show ffe6d61:` accordingly.
- B5: `pyproj = "*"` in `[feature.tests.dependencies]` is justified by the tests, lives next to `cdshealpix` / `shapely` / `awkward`, and has no duplicate in `pyproject.toml` (which has no `tests` extra). The rubric's #137 example that deleted `pyproj` from `pixi.toml` was about a runtime dependency, not a test one. No comment.
- C1: four test functions, but they test one cross-cutting property rather than one function, so `Test<FunctionName>` grouping does not fit, and existing modules (`test_distances.py`, the top of `test_neighbours.py`) also keep loose functions. Rejected. C2 is satisfied (the tests call `nested.vertices` / `nested.neighbours` / `nested.lonlat_to_healpix` directly).
- Rubric gaps: section B has no general "correctness" rule, so the `EPSG:4326` source-CRS comment is filed under B8 ("numeric conventions"), which is a stretch; C4 ("reference implementation for full cases") was the closest fit for asking for the direct centre comparison. Not covered and therefore left out: `side` is the axis-aligned extent / diagonal of the 45°-rotated square (the actual side is `side/√2`), so the name and `diagonal_02 == side` read oddly; `np.nonzero(neighbours >= 0)` on L100 is a no-op for `connectivity="edge"` (never `-1`, per `test_edge_neighbour_topology_for_every_cell`).
- Unrelated and pre-existing, noticed in passing: `.github/workflows/python-ci.yml` still hashes `python/healpix-geo/pyproject.toml` and `python/healpix-geo/pixi.toml` for the pixi lock cache key, paths that no longer exist on `main`.
