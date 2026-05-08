# Restructure: from `hailo-rpi5-examples` fork to a 3-repo Watcher framework

## Context

This repository is currently a fork of `hailo-ai/hailo-rpi5-examples` that has grown four production Watcher applications (bluebox, helen-o-matic, peetronic, pigeonator) on top of the upstream examples. The fork posture is now hindering rather than helping: the name no longer reflects what the code does, the upstream `basic_pipelines/` tree is unused noise, and the four apps share ~70%+ of their code via copy-paste of `static/` web UIs and per-app `web_server.py` route lists, which has produced real drift (e.g. button class renaming `dog`↔`pigeon` repeated across many files; helen-o-matic's clock pages bolted onto its UI rather than as an extension).

The intended outcome is three repos with clear ownership:

- **`bowerhaus/watcher-core`** — public library (Python package: `watcher_core`). Contains the shared detection lifecycle, GStreamer pipelines, web framework, and the parameterized web UI. Pip-installable.
- **`bowerhaus/my-watchers`** — private monorepo holding `helen-o-matic` and `peetronic` (these contain personal/household specifics, custom-trained models, and identifying metadata that should not be public).
- **`bowerhaus/pigeonator`** — public, distributable standalone app. Cleanly separable because pigeonator is a generic "AI-driven pigeon deterrent" product, not a household-specific deployment. **The existing `bowerhaus/pigeonator` repo on GitHub will first be renamed to `bowerhaus/pigeonator-legacy`** (GitHub auto-redirects the old URL); the new restructured app then takes the canonical `bowerhaus/pigeonator` name.

Bluebox is dropped (no longer relevant).

The web UI lives entirely in `watcher-core`, parameterized by config (class label, button sets, theme color) plus a feature-module hook (for things like helen's clock view). This is the single biggest drift-prevention lever, made tractable because the actual diffs between the existing UIs are config-shaped, not structurally divergent (peetronic vs pigeonator differ only in `dog`↔`pigeon` substitution; helen adds 3 routes for a single clock feature).

The migration is **refactor first, split later** — all the structural work happens in the current repo with all three apps next to each other for easy validation; the repo split at the end is a mechanical filter-repo step.

---

## Final architecture

```
bowerhaus/watcher-core           (public, MIT)
├── src/watcher_core/
│   ├── __init__.py
│   ├── base.py                  # WatcherBase (was watcher_base.py)
│   ├── gstreamer.py             # SOURCE/DISPLAY/INFERENCE pipelines (was gstreamer_watcher_app.py)
│   ├── geometry.py
│   ├── logger.py                # was logger_config.py
│   ├── web/
│   │   ├── server.py            # Flask app factory + common routes (was web_server_common.py)
│   │   ├── templates/           # parameterized index.html, login.html, etc.
│   │   ├── static/              # base App.js, styles.css
│   │   └── features/            # opt-in feature modules (clock, etc.)
│   └── tools/prepsort.py
├── tests/                       # the testing/ framework
├── examples/template_app/       # minimal "hello world" watcher
├── setup_env.sh                 # canonical Hailo env setup, sourced by app repos
├── pyproject.toml
├── README.md                    # API docs + how to build a watcher
└── LICENSE                      # MIT

bowerhaus/my-watchers            (private)
├── helen_o_matic/
│   ├── app.py                   # subclasses WatcherBase, registers ClockFeature
│   ├── gstreamer_app.py         # thin override
│   ├── config-example.json
│   ├── config.json              # gitignored
│   ├── secrets.json             # gitignored
│   ├── users.json               # gitignored
│   ├── certificate/             # gitignored
│   ├── models/                  # gitignored, populated by download_models.sh from Releases
│   ├── dog_mask.png
│   ├── start.sh
│   └── download_models.sh
├── peetronic/
│   └── (same shape)
├── requirements.txt             # pins watcher-core via git tag
├── .env-example                 # WATCHER_CORE_PATH for editable dev installs
└── README.md

bowerhaus/pigeonator              (public, MIT)
├── pigeonator/
│   ├── app.py
│   ├── gstreamer_app.py
│   ├── deterrent_manager.py
│   ├── linktap.py
│   ├── config-example.json
│   ├── pigeon_mask.png
│   ├── start.sh
│   └── download_models.sh
├── requirements.txt             # pins watcher-core via git tag
├── docs/                        # user-facing setup docs (Pi 5 install, LinkTap setup)
├── README.md
└── LICENSE                      # MIT
```

Dependency story:
- **Dev**: `pip install -e ../watcher-core` — sibling checkout, live edits.
- **Prod (Pi)**: `pip install git+https://github.com/bowerhaus/watcher-core.git@v0.X.Y` from each app's `requirements.txt`.

Models:
- Each repo publishes its active model + labels as **GitHub Release assets**.
- `download_models.sh` per app fetches the right version into `models/`.
- `models/*.hef` and `models/*-labels.json` are gitignored everywhere.

---

## Production safety model (precedes all phases)

Three Pis are in production, one per app:
- **Pi-pigeon** (this machine): runs `pigeonator`. Auto-starts on desktop login via `~/.config/wayfire.ini` (`watcher = /home/bower/hailo-rpi5-examples/community_projects/watcher/pigeonator/start_watcher_on_login.sh`). Process title `Hailo Detection App`. Killed by `~/hailo-rpi5-examples/kill_watcher.sh`.
- **Pi-helen**: runs `helen-o-matic` (same autostart pattern, different path).
- **Pi-peetronic**: runs `peetronic` (same).

User has confirmed extended downtime is acceptable, so the strategy is straightforward and the safety story can stay simple:

**Phases 0–2 (structural refactor)** happen in a parallel checkout on Pi-pigeon (or any machine — Hailo hardware isn't required for code-level refactoring, only for runtime smoke tests). Production keeps running unaffected from `/home/bower/hailo-rpi5-examples/` because we never modify that directory or its venv.

```
/home/bower/hailo-rpi5-examples/    ← production, left alone
/home/bower/watcher-migration/      ← fresh git clone + fresh venv; all refactoring here
```

When you want to runtime-test the new code on this Pi's actual hardware: stop production (`./kill_watcher.sh`), run the new code from the migration checkout, kill it, restart the production app via its `start_watcher.sh`. No special procedure required — just stop one, start the other.

**Phase 3 (cutover)** is one-shot per Pi: stop production, archive the old checkout, clone the new repos, install, copy over per-deployment data, smoke-test, update wayfire autostart, reboot. Detailed steps in Phase 3 below. If anything breaks, the archived directory is right there to restore.

---

## Phase 0 — Cleanup (in the migration checkout, NOT production)

**Goal:** strip everything that isn't shared infrastructure or one of the 3 surviving apps. Smaller repo = faster Phase 1.

Drop:
- `basic_pipelines/` — upstream Hailo examples (detection.py, pose_estimation.py, instance_segmentation.py, hailo_rpi_common.py, watcher.py).
- `doc/` — upstream documentation; the install guide will be re-authored per repo as needed.
- `resources/` — upstream HEFs (yolov5/yolov8 variants); not used by any Watcher app.
- `tests/` (root) — upstream pytest files (test_advanced.py, test_edge_cases.py, test_hailo_rpi5_examples.py, test_infra.py, test_sanity_check.py).
- `apps/` — empty skeleton at root with `hom/src/{pages,css}` and `pigeonator/src/hooks` (looks like an abandoned React/Next rewrite; no files, only empty dirs — confirm with user it's truly abandoned before deleting).
- `ci.yaml` — upstream CI config.
- `download_resources.sh` — upstream resource downloader (replaced by per-repo `download_models.sh`).
- `community_projects/watcher/bluebox/` — dropped per decision; tag the current `dev` HEAD as `archive/bluebox-final` before deletion so it remains recoverable if needed.
- `community_projects/community_projects.md`, `community_projects/NeoPixel/`, `community_projects/temaplate_example/`, `community_projects/wled_display/` — upstream community examples (not the Watcher framework).
- Stale logs: `hailort.log` at root and committed log files in any `logs/` directories.

Keep and relocate:
- `setup_env.sh` — keep as-is (it's well-debugged; will move to watcher-core in Phase 1).
- `install.sh` — replace with per-repo installs in Phase 3.
- `README.md` — replace per-repo in Phase 3.
- `kill_watcher.sh` — keep at root for now; reassign to watcher-core or my-watchers in Phase 3.

Verify:
- `git status` clean and the three apps still run end-to-end (`./community_projects/watcher/{helen-o-matic,peetronic,pigeonator}/start_watcher.sh`).

---

## Phase 1 — Extract `watcher_core` as an in-repo package (in the migration checkout)

**Goal:** introduce the package boundary without splitting repos. After this phase, all three apps import from a real Python package, installed editably.

Critical files to create/move:
- New top-level `src/watcher_core/` mirroring the final layout above.
- Move `community_projects/watcher/watcher_base.py` → `src/watcher_core/base.py`.
- Move `community_projects/watcher/gstreamer_watcher_app.py` → `src/watcher_core/gstreamer.py`.
- Move `community_projects/watcher/geometry.py` → `src/watcher_core/geometry.py`.
- Move `community_projects/watcher/logger_config.py` → `src/watcher_core/logger.py`.
- Move `community_projects/watcher/web_server_common.py` → `src/watcher_core/web/server.py`.
- Move `community_projects/watcher/tools/prepsort.py` → `src/watcher_core/tools/prepsort.py`.
- Move `community_projects/watcher/testing/` → `tests/` at repo root (keep schemas, test_runner, test_config).

Critical files to write:
- `pyproject.toml` declaring `watcher_core` as a package (uses `setuptools` or `hatchling`); deps include `numpy<2.0.0`, `opencv-python`, `flask`, `gtts`, `playsound`, `loguru`, `pyjwt`, `astral`, `screeninfo`, `setproctitle`, plus `hailo_apps_infra` from git.
- `setup_env.sh` augmented to `pip install -e .` after activating venv.

Critical files to update (each app):
- `community_projects/watcher/{helen-o-matic,peetronic,pigeonator}/<app>.py` — change `from watcher_base import WatcherBase` to `from watcher_core import WatcherBase`. Same for `geometry`, `logger`, etc.
- `community_projects/watcher/{helen-o-matic,peetronic,pigeonator}/web_server.py` — change `from web_server_common import ...` to `from watcher_core.web.server import ...`.
- Each `gstreamer_<app>_app.py` — update imports to `from watcher_core.gstreamer import ...`.

Reuse existing utilities (do NOT rewrite):
- `WatcherBase.start_active_tracking` / `active_tracking` / `stop_active_tracking` lifecycle is solid; preserve API.
- `web_server_common.token_required`, `handle_login`, `handle_metadata_request`, `handle_media`, `handle_delete_files`, `handle_update_json`, `handle_cpu_temperature` — all stay intact, just relocated.
- `SOURCE_PIPELINE` / `DISPLAY_PIPELINE` / `INFERENCE_PIPELINE_WRAPPER` from the watcher-flavored `gstreamer_watcher_app.py` (these are intentional shadows of the `hailo_apps_infra` versions and add USB MJPEG / libcamera / ximagesrc paths) — preserve as-is.

Verify:
- `pip install -e .` from repo root succeeds.
- `pytest tests/` (the relocated testing framework) passes.
- All three apps run: `./community_projects/watcher/helen-o-matic/start_watcher.sh`, etc.
- Each app's web UI loads at its existing port.

---

## Phase 2 — Parameterize the web UI inside `watcher_core` (in the migration checkout)

**Goal:** collapse the three per-app `static/` folders into a single parameterized UI in `watcher_core/web/`. After this phase, each app's `static/` is gone and the UI is configured, not copy-pasted.

Critical files to create:
- `src/watcher_core/web/templates/index.html` — Jinja2 template parameterizing the per-app fields (class labels, button definitions, theme).
- `src/watcher_core/web/templates/login.html` — verbatim from existing (already identical across apps).
- `src/watcher_core/web/static/app.js` — extracted UI logic with config injected via a `<script>` block at template render time.
- `src/watcher_core/web/static/styles.css` — uses CSS custom properties for theme colors (`--accent-yes`, `--accent-no`, `--accent-tag`, etc.).
- `src/watcher_core/web/features/__init__.py` — feature-module registry (`register_feature(name, blueprint, template_dir)`).
- `src/watcher_core/web/features/clock.py` — helen's clock as an opt-in feature: registers `/api/clock_image`, `/clock`, `/review` routes and a `home.html`-equivalent template. Activated by an app passing `features=[ClockFeature]` to the app factory.

Parameterization spec — each app provides an `AppConfig` dataclass:
```python
AppConfig(
    name="pigeonator",
    class_to_track="pigeon",
    review_buttons=[
        Button(label="PIGEON",     value="pigeon", css="yes"),
        Button(label="NOT PIGEON", value=None,     css="no"),
    ],
    theme_color="#3b82f6",
    features=[],  # helen would pass [ClockFeature]
)
```
Helen's button set becomes:
```python
review_buttons=[
    Button(label="HELEN OUT",  value="HELEN OUT",  css="helen-out"),
    Button(label="HELEN BACK", value="HELEN BACK", css="helen-back"),
    Button(label="OUT",        value="OUT",        css="default"),
    Button(label="BACK",       value="BACK",       css="default"),
    Button(label="OTHER",      value="OTHER",      css="default"),
],
features=[ClockFeature],
```

Critical files to delete:
- `community_projects/watcher/helen-o-matic/static/` (4 files: home.html, index.html, login.html, styles.css).
- `community_projects/watcher/peetronic/static/` (4 files including the orphan App.js).
- `community_projects/watcher/pigeonator/static/` (3 files).
- The repeated `web_server.py` files per app become a one-liner: `app = create_watcher_app(AppConfig(...))`.

Critical files to update:
- Each app's `<app>.py` — pass `AppConfig` to the watcher framework; remove direct Flask routing.

**Replace Werkzeug dev server with a production WSGI server.** All three apps currently call `flask.app.run(host=…, port=…, ssl_context=…)` from a daemon thread inside the detection process. This is the Werkzeug development server, and under multi-day uptime alongside the heavy GStreamer + Hailo callback thread it wedges: TCP `accept` keeps succeeding (kernel-side) but the Python accept loop stops servicing new connections, so the TLS handshake never starts. Symptom: `https://<host>:5001` hangs at TLS ClientHello while the detection log keeps recording events normally. Confirmed in production on pi-pigeon 2026-05-07 (~31 hours uptime), recovered only by restarting the watcher.

This must not survive into `watcher_core`. The `create_watcher_app(...)` factory should serve the Flask `app` via [waitress](https://docs.pylonsproject.org/projects/waitress/) (pure-Python, single dependency, prod-grade WSGI). Pattern:

```python
from waitress import serve
serve(app, host=cfg.host, port=cfg.port, url_scheme='https',
      threads=8, channel_timeout=60, _quiet=True)
```

SSL termination: either keep it in-process via a tiny `ssl.SSLContext` wrapper around the listening socket, or punt TLS to a stunnel/nginx sidecar. In-process is simplest — `waitress` itself has no native TLS, but Werkzeug's `make_ssl_devcert` flow we already use is a fine model for wrapping the socket; alternatively run waitress on `127.0.0.1:5001` plaintext and put nginx in front with the existing certs. Decide during Phase 2 implementation; the existing self-signed certs (`<app>.pem` + `<app>-privkey.pem`) carry over either way.

Stop-gap (deliberately NOT applied to production yet — captured here so it's not lost): add `threaded=True` to each app's current `web_server_kwargs` in `<app>.py` so one stuck request can't wedge the whole accept loop. This only mitigates the symptom and is unnecessary once the migration replaces the dev server.

Verify:
- All three apps run with the unified UI; each looks correct (right labels, right colors, right buttons).
- Helen's `/clock` route works exactly as before via the ClockFeature module.
- Manual smoke test: log in, list dates, view event, tag, mark reviewed, delete, download — for all three apps.
- `pytest tests/` still passes.

---

## Phase 3 — Split into three repos

**Goal:** mechanically extract three new repos from the current one. No code changes in this phase.

**Pre-step on GitHub (do this first, before pushing the new pigeonator repo):**
1. Rename `bowerhaus/pigeonator` → `bowerhaus/pigeonator-legacy` via the GitHub repo settings page. GitHub will auto-redirect the old URL.
2. Add a notice to the renamed repo's README pointing to the new `bowerhaus/pigeonator` URL once it exists.
3. Tag the current HEAD of `pigeonator-legacy` (`v0-final` or similar) so the legacy state is recoverable.
4. Now the canonical name `bowerhaus/pigeonator` is free for the new repo.

Approach: use `git filter-repo` to preserve history (but stripped of the deleted upstream/bluebox content). Recommended invocations:

```bash
# From a fresh clone of the current repo, for each target repo:

# 1. watcher-core
git clone --no-local . /tmp/watcher-core
cd /tmp/watcher-core
git filter-repo --path src/watcher_core --path tests --path setup_env.sh --path pyproject.toml --strip-blobs-bigger-than 5M

# 2. my-watchers (helen + peetronic)
git clone --no-local . /tmp/my-watchers
cd /tmp/my-watchers
git filter-repo \
  --path community_projects/watcher/helen-o-matic \
  --path community_projects/watcher/peetronic \
  --path-rename community_projects/watcher/helen-o-matic:helen_o_matic \
  --path-rename community_projects/watcher/peetronic:peetronic \
  --strip-blobs-bigger-than 5M

# 3. pigeonator
git clone --no-local . /tmp/pigeonator
cd /tmp/pigeonator
git filter-repo \
  --path community_projects/watcher/pigeonator \
  --path-rename community_projects/watcher/pigeonator:pigeonator \
  --strip-blobs-bigger-than 5M
```

The `--strip-blobs-bigger-than 5M` cleans accumulated `.hef` blobs from history at the same time, keeping the new repos small.

Critical files to write per new repo:
- `README.md` — purpose, install, run, link to watcher-core.
- `requirements.txt` — `git+https://github.com/bowerhaus/watcher-core.git@v0.1.0` plus app-specific deps (e.g. `requests` for pigeonator's LinkTap client).
- `LICENSE` — MIT for watcher-core and pigeonator; my-watchers stays unlicensed (private).
- `.gitignore` — add `models/*.hef`, `models/*-labels.json`, `config.json`, `secrets.json`, `users.json`, `certificate/`, `output/`, `logs/`.
- `download_models.sh` per app repo (curl from the app's GitHub Releases asset URL).
- Pi-side `start.sh` updated to `pip install -r requirements.txt` rather than `source ../setup_env.sh`.

Tag versions:
- `bowerhaus/watcher-core` → `v0.1.0`.
- App `requirements.txt` pins to that tag.

Verify (per repo):
- Fresh clone + `pip install -e ../watcher-core` (dev) or `pip install -r requirements.txt` (prod) succeeds.
- `./download_models.sh` retrieves the model.
- `./start.sh` runs the app and the web UI loads.
- The original repo can now be archived (rename to `hailo-rpi5-examples-archive` or similar) on GitHub for reference.

### Per-Pi cutover

Each of the 3 Pis gets the same procedure. Order doesn't matter much given relaxed downtime, but doing them one at a time means you only debug one thing at once.

Per Pi (with `<APP>` and `$APP_REPO` substituted appropriately):

```bash
# Stop production and archive its directory.
~/hailo-rpi5-examples/kill_watcher.sh
mv ~/hailo-rpi5-examples ~/hailo-rpi5-examples-archive

# Clone the new repos.
git clone https://github.com/bowerhaus/watcher-core.git ~/watcher-core
git clone $APP_REPO ~/<APP>            # ~/pigeonator, ~/my-watchers, etc.

# Install (the editable-install pattern works the same on prod as it does in dev).
cd ~/<APP>
source ~/watcher-core/setup_env.sh     # activates venv, sets DEVICE_ARCHITECTURE
pip install -e ~/watcher-core
pip install -r requirements.txt
./download_models.sh

# Copy per-deployment data from the archive (config, secrets, users, certs, event history).
ARCHIVE=~/hailo-rpi5-examples-archive/community_projects/watcher/<APP>
cp $ARCHIVE/config.json $ARCHIVE/secrets.json $ARCHIVE/users.json .
cp -r $ARCHIVE/certificate $ARCHIVE/output .

# Smoke-test, then update wayfire autostart, then reboot.
./start_watcher.sh                     # confirm web UI loads, detection works
pkill -f Hailo
$EDITOR ~/.config/wayfire.ini          # update the `watcher = ...` line to the new path
sudo reboot                            # validate autostart
```

If the new app fails in a way that isn't quick to fix: `mv ~/hailo-rpi5-examples-archive ~/hailo-rpi5-examples` restores production exactly as it was. Revert wayfire.ini, reboot, you're back. Keep the archive directory around for a few weeks before deleting.

---

## Phase 4 — Models distribution

**Goal:** ship models via GitHub Releases instead of in-repo binaries.

Per repo:
- Create a v0.1.0 release on GitHub.
- Upload the active model + labels as release assets:
  - `pigeonator`: `pigeonator-mk3-b.v4.yolov8p.hef` + `pigeonator-mk3-b.v3-labels.json`.
  - `my-watchers/helen-o-matic`: `helen-o-matic.v7.yolov8p.hef` + `helen-o-matic.v5-labels.json` (release on the my-watchers repo, asset path keyed by app subfolder, e.g. `helen-o-matic-v0.1.0.hef`).
  - `my-watchers/peetronic`: `peetronic.v1.yolov8p.hef` + `peetronic.v1-labels.json`.
- `download_models.sh` per app: `curl -L -o models/<file> https://github.com/bowerhaus/<repo>/releases/download/<tag>/<file>`.

Verify:
- Fresh Pi can clone an app repo, run `./download_models.sh`, then `./start.sh`, with no manual file copying.
- The active app behavior matches pre-migration (same detection rate, same metadata).

---

## Open items to confirm before executing

1. **`apps/` skeleton** — confirm the empty `apps/hom/src/{pages,css}` and `apps/pigeonator/src/hooks` directories at the repo root are an abandoned experiment and safe to delete (no in-progress work depends on them).
2. **History preservation vs squash** — Phase 3 above preserves filtered history. The alternative is a clean `git init` per new repo with one squash commit ("Extract from hailo-rpi5-examples"). History-preserving is recommended (you keep `git blame` for the era this code already had); squash is only worth it if the existing history is something you want to disown.
3. **watcher-core license** — defaulting to MIT (matches the upstream repo and is consistent with Hailo's example license). Confirm this is what you want for the public library.
4. **bluebox final state** — confirm tagging `archive/bluebox-final` before deletion is sufficient (vs. extracting bluebox to its own archived repo).

---

## Verification end-to-end (post-Phase 4)

The migration is complete when:

- All three repos exist on GitHub, with correct visibility (watcher-core + pigeonator public, my-watchers private).
- A fresh Raspberry Pi 5 can stand up any of the three apps via:
  ```bash
  git clone <app-repo>
  cd <app-repo>
  source setup_env.sh    # provided by watcher-core via the dependency or pulled per repo
  pip install -r requirements.txt
  ./download_models.sh
  cp config-example.json config.json && $EDITOR config.json
  ./start.sh
  ```
- Web UI of each app loads, login works, events list/tag/review/delete works, video playback works, CPU temp display works.
- Helen's clock view loads at `/clock`.
- Pigeonator's LinkTap deterrent triggers correctly on a sustained detection (with WATERING_ON=true).
- `pytest` passes in `watcher-core`.
- The original `bowerhaus/hailo-rpi5-examples` repo is renamed (e.g. `hailo-rpi5-examples-archive`) and read-only, with the final commit pointing to the new repo URLs in its README.
