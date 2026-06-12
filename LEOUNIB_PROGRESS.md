# Leounib Odysseus Progress

Last updated: 2026-06-12

## Branches

- `leounib-main`
  - Personal integration branch on the `JuusBocks/odysseus` fork.
  - Current app version: `1.1.0`.
  - Latest feature integration commit before version bump: `634102c`.
  - Includes latest fetched `upstream/dev` at `9d7a3d6`.
  - Use this as the personal production branch.

- `leounib-dev`
  - Personal development branch for dated feature branch integration.
  - Keep synced with `upstream/dev` before promoting to nonprod.
  - Current app version: `1.1.0`.

- `leounib-nonprod`
  - Personal validation branch for smoke tests and manual UI checks.
  - Promote into `leounib-main` only after nonprod checks pass.
  - Current app version: `1.1.0`.

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

## Version Tracking

- Current app version: `1.1.0`.
- Current UI version indicator: `v1.1.0 · <commit>`.
- Version source of truth: `APP_VERSION` in `src/constants.py`, surfaced by `/api/version`.
- Version bump rule:
  - Patch (`x.y.Z`) for bug fixes, docs, and workflow-only corrections.
  - Minor (`x.Y.0`) for user-visible features, UI additions, new endpoints, or release-cycle automation.
  - Major (`X.0.0`) for breaking behavior, migration-heavy changes, or incompatible deployment changes.
- Reason for `1.1.0`: added user-visible sidebar version visibility, sidebar hardware/model status, and verified promotion automation.

## Current Feature Progress

- Added a three-stage personal software cycle:
  - `leounib-dev`: development / integration.
  - `leounib-nonprod`: validation and smoke testing.
  - `leounib-main`: production / latest tested changes.
- Added `nonprod`, `leounib-dev`, and `leounib-nonprod` branches.
- Added GitHub Actions CI coverage for `dev`, `nonprod`, `main`, `leounib-dev`, `leounib-nonprod`, and `leounib-main`.
- Added GitHub Actions **Promote verified changes** manual workflow:
  - `nonprod` verifies `leounib-dev` and fast-forwards `leounib-nonprod`.
  - `prod` verifies `leounib-nonprod` and fast-forwards `leounib-main`.
  - Promotions use `git merge --ff-only`, so production only moves to changes that already passed through the prior branch.
- Added app smoke checks for environment branches:
  - Python compile.
  - JS syntax check.
  - App boot with auth disabled.
  - `/api/health`, `/api/runtime`, and `/api/dashboard/system` endpoint checks.
- Fixed Docker publish to lowercase the GHCR package name from `JuusBocks/odysseus` to `juusbocks/odysseus`.
- Added main sidebar System dashboard:
  - RAM availability.
  - GPU / CPU-only status.
  - Local Ollama loaded-model residency.
- Added `/api/dashboard/system` as a read-only status endpoint for the sidebar dashboard.
- Added persistent sidebar version indicator backed by `/api/version`.
- Bumped service worker cache to refresh the updated UI assets.
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

- Python compile check passed for changed backend files:
  - `app.py`
  - `routes/admin_wipe_routes.py`
  - `routes/hwfit_routes.py`
- `static/app.js` syntax check passed.
- Odysseus was restarted from `leounib-main` and confirmed listening on `*:7860`.
- Automatic warmup was verified to leave `llama3.2:3b` resident in Ollama.
- GitHub Actions **Promote verified changes** is active and visible in the Actions tab.
- GitHub Actions **ci / docker publish** passed after the GHCR lowercase image-name fix:
  - `build (amd64)` passed.
  - `build (arm64)` passed.
  - `merge manifest + tag` passed.
- `upstream` push remains disabled; pushes go to `origin` only.
- `dev`, `leounib-dev`, `leounib-nonprod`, and `leounib-main` were pushed to `origin`.

## Automation Updates

- `.github/workflows/ci.yml`
  - Runs on `dev`, `nonprod`, `main`, `leounib-dev`, `leounib-nonprod`, and `leounib-main`.
  - Resolves environment name as `dev`, `nonprod`, or `prod`.
  - Runs app smoke checks for environment branch pushes.

- `.github/workflows/promote.yml`
  - Manual workflow shown as **Promote verified changes** in GitHub Actions.
  - `target=nonprod`: verify `origin/leounib-dev`, then fast-forward `leounib-nonprod`.
  - `target=prod`: verify `origin/leounib-nonprod`, then fast-forward `leounib-main`.

- `.github/workflows/docker-publish.yml`
  - Normalizes `GITHUB_REPOSITORY` to lowercase before pushing to GHCR.
  - Publishes valid image refs such as `ghcr.io/juusbocks/odysseus`.

## Recent Commits

- `0f80144 ci(release): add verified promotion workflow`
- `4e7bfd6 ci(docker): lowercase ghcr image name`
- `7ce1b54 docs(progress): capture release automation updates`
- `634102c feat(ui): show running version in sidebar`

## Merged Feature Branches

- `codex/local-runtime-controls` -> `leounib-main` as merge commit `6d8cca4`.
- `codex/automatic-model-warmup` -> `leounib-main` as merge commit `791e2e9`.
- `codex/safe-manual-model-warmup` -> `leounib-main` as merge commit `2783efc`.

## Recommended Workflow

1. Fetch upstream updates regularly.
2. Keep personal work on dated feature branches using `codex/YYYYMMDD-short-description`, for example `codex/20260612-local-runtime-controls`.
3. Merge feature branches into `leounib-dev` after focused testing.
4. Promote `leounib-dev` to `leounib-nonprod` and run smoke tests before any production push.
5. Promote `leounib-nonprod` to `leounib-main` / production only after the nonprod checks pass.
6. Push only to `origin` unless intentionally opening an upstream PR.

Useful commands:

```bash
git fetch upstream
git switch leounib-dev
git merge upstream/dev
git push origin leounib-dev

git switch leounib-nonprod
git merge leounib-dev
git push origin leounib-nonprod

git switch leounib-main
git merge leounib-nonprod
git push origin leounib-main
```

Nonprod smoke checklist:

- App starts cleanly and reports healthy.
- Login/auth flow works.
- Model endpoint list loads.
- Local model residency/warmup status is visible when Ollama is configured.
- A normal chat can send and receive a response.
- Any changed UI flow is checked in the browser before production promotion.

GitHub Actions promotion:

- Use **Actions -> Promote verified changes -> Run workflow -> nonprod** to verify `leounib-dev` and fast-forward `leounib-nonprod`.
- Use **Actions -> Promote verified changes -> Run workflow -> prod** to verify `leounib-nonprod` and fast-forward `leounib-main`.
- The workflow refuses non-fast-forward promotion, so prod only moves to changes that already passed through the previous branch.

## Next Likely Step

Keep `leounib-dev` synced with `upstream/dev`, validate releases in `leounib-nonprod`, and promote to `leounib-main` only after the smoke checklist passes.
