# Leounib Odysseus Progress

Last updated: 2026-06-12

## Branches

- `leounib-main`
  - Personal integration branch on the `JuusBocks/odysseus` fork.
  - Current branch tip: `420e960`.
  - Latest feature integration tip: `2783efc`.
  - Includes latest fetched `upstream/dev` at `9d7a3d6`.
  - Use this as the local "second main" branch for merging personal features.

- `codex/local-runtime-controls`
  - Feature branch pushed to `origin` and merged into `leounib-main`.
  - Contains local runtime controls, safe shutdown status, and Ollama model warmup UI.
  - Latest commit: `c9a7c92 fix(settings): keep model warmup lightweight`.

- `codex/automatic-model-warmup`
  - Feature branch pushed to `origin` and merged into `leounib-main`.
  - Adds automatic local model warmup after Odysseus startup.
  - Latest commit: `3ef3a5c fix(settings): leave default model warm after startup`.

- `codex/safe-manual-model-warmup`
  - Feature branch pushed to `origin` and merged into `leounib-main`.
  - Splits manual warmup into recommended models and explicit all-model loading.
  - Latest commit: `3f1e5ca fix(settings): make manual model warmup safer`.

## Current Feature Progress

- Added Settings -> System -> App Runtime status.
- Added safe shutdown button for the local Odysseus launchd service.
- Added backup export marker so Settings can show the last export time.
- Added local Ollama model warmup controls.
- Added warmup progress bar and resident-model status.
- Automatic warmup starts after Odysseus startup and is sequential.
- Automatic warmup loads recommended models only, then reloads the default small model:
  - `llama3.2:3b`
  - `qwen3:8b`
  - `deepseek-r1:8b`
  - `qwen3:14b`
  - `deepseek-r1:14b`
- Settings exposes two manual actions:
  - `Load Recommended Models`: warms the safe/snappy set.
  - `Load All Models`: explicit confirmed action for the full local model list, including `qwen3:30b` and `deepseek-r1:32b`.
- Current local defaults:
  - Default chat model: `llama3.2:3b`
  - Fallbacks: `qwen3:8b`, then `qwen3:14b`
  - DeepResearch model: `deepseek-r1:14b`

## Verification

- Python compile check passed for changed backend files.
- `static/js/admin.js` syntax check passed.
- Odysseus was restarted from `leounib-main` and confirmed listening on `*:7860`.
- Automatic warmup was verified to leave `llama3.2:3b` resident in Ollama.
- `upstream` push remains disabled; pushes go to `origin` only.
- `leounib-main` was pushed to `origin/leounib-main`.

## Merged Feature Branches

- `codex/local-runtime-controls` -> `leounib-main` as merge commit `6d8cca4`.
- `codex/automatic-model-warmup` -> `leounib-main` as merge commit `791e2e9`.
- `codex/safe-manual-model-warmup` -> `leounib-main` as merge commit `2783efc`.

## Recommended Workflow

1. Fetch upstream updates regularly.
2. Keep personal work on feature branches.
3. Merge `upstream/dev` into `leounib-main`.
4. Merge feature branches into `leounib-main` after testing.
5. Push only to `origin` unless intentionally opening an upstream PR.

Useful commands:

```bash
git fetch upstream
git switch leounib-main
git merge upstream/dev
git push origin leounib-main
```

## Next Likely Step

Keep `leounib-main` synced with `upstream/dev`, and create a new feature branch for each future feature, fix, or bug.
