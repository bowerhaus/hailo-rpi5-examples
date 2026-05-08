# Progress: Restructure into three repos

> **How to resume:** prompt `resume from progress.md`. Context-resilient — keep this file accurate after every meaningful step.

## Plan
- File: [plans/001-restructure-into-three-repos.md](plans/001-restructure-into-three-repos.md)
- Approved: 2026-05-06
- GitHub issue: [#5](https://github.com/bowerhaus/hailo-rpi5-examples/issues/5) (label: `enhancement`)
- PR for this branch must include `Closes #5` in the body to auto-close the issue on merge.

## Branch
- Working branch: `restructure-into-three-repos` (created from `dev` on 2026-05-06)
- Base branch for PR: `dev`
- Current branch confirmed: `restructure-into-three-repos`

## Working conventions for this plan
- Do **not** auto-stage changes — user stages manually.
- No "what-was-here" comments per `.github/copilot-instructions.md`.
- Three Pis are in production; refactor work happens in a parallel checkout (`~/watcher-migration/`) — never touch `~/hailo-rpi5-examples/` directly. (See plan "Production safety model" section.)
- Bluebox is being dropped — tag `archive/bluebox-final` before any deletion.

## Open items to resolve before / during execution
From plan §"Open items to confirm before executing":
1. [ ] Confirm `apps/` skeleton (`apps/hom/src/...`, `apps/pigeonator/src/hooks`) is abandoned and safe to delete.
2. [ ] Decide history-preservation (recommended) vs squash for Phase 3 split.
3. [ ] Confirm `watcher-core` license = MIT.
4. [ ] Confirm tagging `archive/bluebox-final` is sufficient (vs. extracting to a separate archived repo).

## Phase checklist

### Phase 0 — Cleanup (in migration checkout)
- [ ] Tag `archive/bluebox-final` at current `dev` HEAD.
- [ ] Delete `basic_pipelines/`.
- [ ] Delete `doc/`.
- [ ] Delete `resources/`.
- [ ] Delete root `tests/` (upstream pytest).
- [ ] Delete `apps/` (after confirming open item #1).
- [ ] Delete `ci.yaml`.
- [ ] Delete `download_resources.sh`.
- [ ] Delete `community_projects/watcher/bluebox/`.
- [ ] Delete `community_projects/community_projects.md`, `NeoPixel/`, `temaplate_example/`, `wled_display/`.
- [ ] Delete `hailort.log` and committed `logs/` content.
- [ ] Verify three apps still run end-to-end (helen-o-matic, peetronic, pigeonator).

### Phase 1 — Extract `watcher_core` as in-repo package
- [ ] Create `src/watcher_core/` skeleton (per plan layout).
- [ ] Move `watcher_base.py` → `src/watcher_core/base.py`.
- [ ] Move `gstreamer_watcher_app.py` → `src/watcher_core/gstreamer.py`.
- [ ] Move `geometry.py` → `src/watcher_core/geometry.py`.
- [ ] Move `logger_config.py` → `src/watcher_core/logger.py`.
- [ ] Move `web_server_common.py` → `src/watcher_core/web/server.py`.
- [ ] Move `tools/prepsort.py` → `src/watcher_core/tools/prepsort.py`.
- [ ] Move testing framework → root `tests/`.
- [ ] Write `pyproject.toml` (deps: numpy<2, opencv-python, flask, gtts, playsound, loguru, pyjwt, astral, screeninfo, setproctitle, hailo_apps_infra).
- [ ] Augment `setup_env.sh` to `pip install -e .`.
- [ ] Update each app's imports (`watcher_base`→`watcher_core`, etc.).
- [ ] Verify `pip install -e .` succeeds.
- [ ] Verify `pytest tests/` passes.
- [ ] Verify all three apps run; web UIs load.

### Phase 2 — Parameterize the web UI
- [ ] Create `web/templates/index.html` (Jinja2, parameterized).
- [ ] Create `web/templates/login.html`.
- [ ] Create `web/static/app.js` with config injection.
- [ ] Create `web/static/styles.css` using CSS custom properties for theming.
- [ ] Create `web/features/__init__.py` (registry).
- [ ] Create `web/features/clock.py` (helen's clock as opt-in feature).
- [ ] Define `AppConfig` dataclass + `Button` model.
- [ ] Convert each app's `<app>.py` to pass `AppConfig`; collapse `web_server.py` to one-liner.
- [ ] Delete per-app `static/` folders (helen, peetronic, pigeonator).
- [ ] Verify all three apps render correct labels/colors/buttons.
- [ ] Verify helen's `/clock` works via ClockFeature.
- [ ] Smoke test: login, list, view, tag, mark reviewed, delete, download (all 3 apps).
- [ ] `pytest tests/` still passes.

### Phase 3 — Split into three repos
- [ ] GitHub: rename `bowerhaus/pigeonator` → `bowerhaus/pigeonator-legacy`, tag `v0-final`, add notice in README.
- [ ] `git filter-repo` extract `watcher-core`.
- [ ] `git filter-repo` extract `my-watchers` (helen + peetronic).
- [ ] `git filter-repo` extract new `pigeonator`.
- [ ] Write per-repo `README.md`, `requirements.txt`, `LICENSE` (MIT for core+pigeonator; none for my-watchers).
- [ ] Per-repo `.gitignore` (models, config, secrets, certs, output, logs).
- [ ] Per-app `download_models.sh` (curl from Releases).
- [ ] Update each `start.sh` to `pip install -r requirements.txt`.
- [ ] Tag `watcher-core@v0.1.0`; pin app `requirements.txt`.
- [ ] Per-Pi cutover: pi-pigeon, pi-helen, pi-peetronic (one at a time).

### Phase 4 — Models distribution
- [ ] Create v0.1.0 release on each repo.
- [ ] Upload `.hef` + labels JSON as release assets.
- [ ] Wire `download_models.sh` to release URLs.
- [ ] Verify fresh-Pi flow: clone → setup_env → install → download_models → start.

## Verification end-to-end
- [ ] All three repos exist on GitHub with correct visibility.
- [ ] Fresh Pi 5 stand-up works for any app.
- [ ] All web UI features work for all three apps.
- [ ] Helen's `/clock` works.
- [ ] Pigeonator LinkTap deterrent triggers on sustained detection.
- [ ] `pytest` passes in `watcher-core`.
- [ ] Original `hailo-rpi5-examples` repo renamed and made read-only with pointer to new repos.

## Activity log
- 2026-05-06: Plan saved to `plans/001-restructure-into-three-repos.md`.
- 2026-05-06: Branch `restructure-into-three-repos` created from `dev`.
- 2026-05-06: progress.md initialized; awaiting context reset before Phase 0.
- 2026-05-07: GitHub issues enabled on `bowerhaus/hailo-rpi5-examples` (was disabled by fork default); issue [#5](https://github.com/bowerhaus/hailo-rpi5-examples/issues/5) created (`enhancement`).
