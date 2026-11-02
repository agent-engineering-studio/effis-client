# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-11-02

### Added

- Burnt-area perimeters from the EFFIS WFS: `fetch_perimeters`, with the
  pure `perimeters_params` / `parse_perimeters` / `feature_date`. Dates are
  filtered locally; `Perimeters.truncated` flags a response at the cap.
- The official FWI chain from the EFFIS WMS: `fetch_fwi`, with the pure
  `fwi_params` / `check_tiff` / `sample_fwi` (extra `raster`). An all-zero
  raster is `None`, not a calm day.
- `EffisError` for MapServer errors served as HTTP 200, with the exception
  code and message extracted.
- Extracted from Limen (`src/limen/integrations/effis/` at 97ed93e) and
  relicensed under Apache-2.0 by its sole author; the API is new: the
  caller's `httpx.AsyncClient` is injected and errors propagate instead of
  degrading to an empty result.
