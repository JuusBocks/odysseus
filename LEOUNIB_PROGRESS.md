# Leounib Odysseus Progress

Last updated: 2026-06-12

## Branches

- `leounib-main`
  - Personal integration branch on the `JuusBocks/odysseus` fork.
  - Based on latest fetched `upstream/dev` at `9d7a3d6`.
  - Use this as the local "second main" branch for merging personal features.

- `codex/local-runtime-controls`
  - Feature branch pushed to `origin`.
  - Contains local runtime controls, safe shutdown status, and Ollama model warmup UI.
  - Latest commit: `c9a7c92 fix(settings): keep model warmup lightweight`.

## Current Feature Progress

- Added Settings -> System -> App Runtime status.
- Added safe shutdown button for the local Odysseus launchd service.
- Added backup export marker so Settings can show the last export time.
- Added "Load Local Models" warmup control for local Ollama models.
- Added warmup progress bar and resident-model status.
- Warmup is manual-only and sequential to keep Odysseus responsive.
- Warmup priority loads small/daily models before heavier reasoning models:
  - `llama3.2:3b`
  - `qwen3:8b`
  - `deepseek-r1:8b`
  - `qwen3:14b`
  - `deepseek-r1:14b`
  - `qwen3:30b`
  - `deepseek-r1:32b`

## Verification

- Python compile check passed for changed backend files.
- `static/js/admin.js` syntax check passed.
- Odysseus was restarted and confirmed listening on `*:7860`.
- `upstream` push remains disabled; pushes go to `origin` only.

## Recommended Workflow

1. Keep pulling/fetching upstream updates into `leounib-main`.
2. Keep personal work on feature branches.
3. Merge feature branches into `leounib-main` after testing.
4. Push only to `origin` unless intentionally opening an upstream PR.

## Next Likely Step

Merge `codex/local-runtime-controls` into `leounib-main` when ready, then resolve any upstream drift if new `upstream/dev` commits arrive first.
