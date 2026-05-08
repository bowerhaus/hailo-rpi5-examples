# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment setup

The Python virtual environment, TAPPAS post-processing path, and `DEVICE_ARCHITECTURE` env var must be set before running anything. Always begin a session with:

```bash
source setup_env.sh
```

`setup_env.sh` must be sourced (not executed). It detects whether the system uses `hailo-tappas-core` (Pi 5) or full `hailo_tappas`, picks the correct virtualenv (`venv_hailo_rpi5_examples` for Pi 5), creates it on first run, and queries `hailortcli` to set `DEVICE_ARCHITECTURE` (`hailo8` or `hailo8l`). If the device is not reachable, the script returns non-zero and downstream commands will fail.

Initial install: `./install.sh` (also sources `setup_env.sh`, installs `requirements.txt`, runs `download_resources.sh`). Pass `--all` to download all HEFs, `--test` to install test deps.

## Common commands

| Task | Command |
|---|---|
| Run upstream basic pipelines | `python basic_pipelines/{detection,pose_estimation,instance_segmentation}.py` |
| Run with RPi camera | append `--input rpi` |
| Run with USB camera | `--input /dev/videoN` (use `get-usb-camera` to find N) |
| Run all tests | `./run_tests.sh` |
| Run a single test file | `pytest tests/test_sanity_check.py --log-cli-level=INFO` |
| Dump GStreamer pipeline graph | append `--dump-dot` to any pipeline script (writes `pipeline.dot` next to the script) |

The Watcher applications (see below) each have their own `start_watcher.sh` that sources `setup_env.sh`, `cd`s into the app folder, and launches with the right HEF and labels.

## Architecture: two layers

**Layer 1 — basic_pipelines/** is the upstream Hailo example layer. Each script (`detection.py`, `pose_estimation.py`, `instance_segmentation.py`) is a small file that:
1. Subclasses `app_callback_class` (from `hailo_apps_infra.hailo_rpi_common`) to add user state,
2. Defines an `app_callback(pad, info, user_data)` that runs on every GStreamer buffer,
3. Instantiates a `GStreamer*App` from `hailo_apps_infra` and calls `.run()`.

All real pipeline construction lives in the **`hailo_apps_infra`** pip package (installed from `git+https://github.com/hailo-ai/hailo-apps-infra.git` via `requirements.txt`) — when modifying pipeline behavior, that package is the source, not files in this repo. `basic_pipelines/hailo_rpi_common.py` is a near-duplicate of the package version kept around for the local `watcher.py` example; prefer importing from `hailo_apps_infra` in new code.

The pipeline pattern is: `SOURCE_PIPELINE → INFERENCE_PIPELINE_WRAPPER(INFERENCE_PIPELINE) → tracker → USER_CALLBACK_PIPELINE → DISPLAY_PIPELINE`. The `hailocropper`/`hailoaggregator` wrapper preserves the original frame resolution while feeding the network its required input size.

**Layer 2 — community_projects/watcher/** is this fork's Watcher framework, the heart of the active development work. Read this section before making changes here.

## Watcher framework (community_projects/watcher/)

Four production applications share a common base: **bluebox**, **helen-o-matic**, **peetronic**, **pigeonator**. They are not toy examples — each runs as a long-lived service on a Pi 5 with its own web UI on a different port, SSL cert, user auth, and tracked output directory.

### Shared modules (at watcher/ root)
- `watcher_base.py` — `WatcherBase(app_callback_class)` is the parent for every app's main class. Implements detection debouncing (`CLASS_DETECTED_COUNT` / `CLASS_GONE_SECONDS`), centroid/velocity tracking, masking via `{class}_mask.png` (B=255 R=255 pixels = active region), event lifecycle (`start_active_tracking` → `active_tracking` per-frame → `stop_active_tracking` → metadata + video + image written), and ffmpeg conversion of `.m4v` to web-friendly H264 `.mp4`.
- `gstreamer_watcher_app.py` — overrides `SOURCE_PIPELINE` / `DISPLAY_PIPELINE` to add USB MJPEG decode, `libcamera`/`appsrc` paths, `ximagesrc` (X11 desktop capture), screen-fitting display sink, and astral-based daytime detection.
- `web_server_common.py` — JWT auth (key from `secrets.json`), users from `users.json`, plus `handle_*` helpers for media listing, metadata CRUD, login, CPU temp endpoints. Each app's `web_server.py` is a thin Flask app that wires routes to these handlers.
- `geometry.py`, `logger_config.py` (loguru, daily-rotated logs in `logs/`).

### Per-app structure
Each app folder (`pigeonator/`, `helen-o-matic/`, `peetronic/`, `bluebox/`) contains:
- `<app>.py` — main entry, subclasses `WatcherBase` and overrides `active_tracking` / `create_metadata` / `stop_active_tracking` to add app-specific behavior (e.g. `pigeonator` triggers `DeterrentManager` via the LinkTap API after `DETER_DELAY_SECONDS`).
- `gstreamer_<app>_app.py` — subclasses `GStreamerDetectionApp` / similar.
- `config.json` — runtime config (gitignored if it contains secrets); `config-example.json` is the committed template.
- `secrets.json` (JWT secret), `users.json` (hashed passwords).
- `models/` — `.hef` model + `*-labels.json`.
- `certificate/` — self-signed SSL certs (`<app>.pem` + `<app>-privkey.pem`).
- `static/` — Flask-served web UI (`index.html`, `App.js`, `styles.css`, `login.html`).
- `output/` — `YYYYMMDD/` subdirs, each event written as a triple: `<timestamp>_<class>.{mp4,jpg,json}`. Output dir can be overridden by env var `WATCHER_OUTPUT_DIRECTORY`.
- `start_watcher.sh` + `start_watcher_on_login.sh` — production launch scripts.

The config file path can be overridden by env var `WATCHER_CONFIG_FILE` (used by the test runner to swap configs).

### Testing the Watcher apps
Separate from the upstream `tests/` directory. Located at `community_projects/watcher/testing/`:

```bash
cd community_projects/watcher
python -m testing.test_runner                       # all tests
python -m testing.test_runner --test-name <name>    # single
python -m testing.test_runner --interactive         # pick from filtered list
python -m testing.test_runner --filter "app_type=helen-o-matic"
```

Test cases are defined in `testing/test_config.py`; each plays an MP4 through the app and validates the resulting JSON metadata against `testing/schemas/metadata_schema.json` plus per-test `expected_metadata` / `expected_classes` percentages / optional `custom_validation` callbacks.

## Plan-driven workflow

- Plans live in `plans/` with an integer prefix (e.g. `001-restructure-into-three-repos.md`). They are the durable, long-lived record of intent — additions, decisions, and lessons-learned-during-implementation belong **in the plan**.
- `progress.md` (at repo root, when present) is **ephemeral**. It tracks step-by-step status for the currently-active plan only and is wiped when the plan's branch is merged into `main`. Do **not** put anything in `progress.md` that needs to survive past the next merge — long-lived context goes in the plan, in CLAUDE.md, or in memory.
- When a discovery during implementation is structural (e.g. "the new system must replace X with Y"), update the relevant plan file. When it's status-tracking ("step 3 done, step 4 next"), update `progress.md`.

## Conventions specific to this fork

- **No "what-was-here" comments.** Per `.github/copilot-instructions.md`: don't include comments that reference what the original line said. Replace, don't annotate.
- **Two `hailo_rpi_common` modules exist** — the one inside `basic_pipelines/` and the one inside the `hailo_apps_infra` pip package. The Watcher apps import from `hailo_apps_infra.hailo_rpi_common`; only `basic_pipelines/watcher.py` imports the local copy. Match the existing import style of the file you're editing.
- **App-specific `gstreamer_*_app.py`** files often re-define `SOURCE_PIPELINE` / `DISPLAY_PIPELINE` with the same name as the infra-package functions — this is intentional shadowing to add features (e.g. webcam MJPEG, screen capture). Don't rename.
- **`config.json` is per-deployment.** When adding a new tunable, also add it to `config-example.json` with a sensible default and to the relevant README.

## Per-deployment runtime patches (not committable)

Some deployments need runtime tweaks to upstream code under `venv_hailo_rpi5_examples/lib/python3.11/site-packages/hailo_apps_infra/`. These **cannot** be committed because the file is wiped by `install.sh`, `pip install --upgrade hailo-apps-infra`, or any venv rebuild. Track them here so the patch can be re-applied after a venv reset.

### Lawn Pigeonator: capture at 15 fps (thermal mitigation)

**Why.** The lawn-deployed Pi 5 was running at ~77°C with the fan at max (4/4) because continuous YOLOv8s inference at 30 fps saturated the Active Cooler. Halving the camera capture rate drops the SoC to ~65°C with the fan at 2/4 while still detecting birds reliably. Inserting a `videorate max-rate=15` element after `appsrc` in our own `SOURCE_PIPELINE` was tried first and failed: `appsrc` returned `GST_FLOW_ERROR -5` and the pipeline crashed. The fix has to live inside `picamera_thread` itself, which is in upstream territory.

**Three edits** to `venv_hailo_rpi5_examples/lib/python3.11/site-packages/hailo_apps_infra/gstreamer_app.py` (inside `picamera_thread`):
1. `controls = {'FrameRate': 30}` → `15`
2. `f"framerate=30/1, pixel-aspect-ratio=1/1"` → `framerate=15/1`
3. `buffer_duration = Gst.util_uint64_scale_int(1, Gst.SECOND, 30)` → `15`

All three matter — without (3) the buffer PTS won't match real capture cadence and downstream elements may drop frames. Without (2) the GStreamer caps disagree with actual rate and negotiation can fail.

**Companion change in committed code:** the lawn Pi's `pigeonator/config.json` (gitignored) sets `FRAME_RATE: 15` so saved MP4 metadata matches the real capture rate. Without it, recordings play back at 2× speed.

**Proper long-term fix.** Plumb a `picamera_config` argument from `GStreamerDetectionApp.__init__` through to `picamera_thread()` so Watcher apps can pass `controls = {'FrameRate': N}` from their config. That's an upstream PR against `hailo-apps-infra` and would let us commit `INFERENCE_FRAME_RATE` as a real config option.
