# Plan: Headless mode for Watcher apps (Raspberry Pi OS Lite)

## Context

The four Watcher services (bluebox, helen-o-matic, peetronic, pigeonator) are designed around an X11 desktop session: the GStreamer pipeline ends in an `xvimagesink` window, the screen size is probed via `screeninfo.get_monitors()`, and a TTS alert is played through `playsound` on every detection event. In practice the operator only ever interacts with the apps via the per-app HTTPS Flask UI on a different port — the local window and audio cue are debug aids, not product features.

This makes it impossible to deploy a Watcher onto a Raspberry Pi 5 running Raspberry Pi OS **Lite** (no desktop, no X11/Wayland, no PulseAudio user session), even though every other component (Hailo inference, libcamera/USB capture, Flask web UI, file output, ffmpeg conversion) is headless-clean. A headless Lite install gives lower idle CPU/RAM, a smaller attack surface, faster boot, and avoids the X11 packages that the Watcher apps don't actually need.

The goal of this plan is to add a single `HEADLESS` switch (config + env var) that:
- skips `screeninfo.get_monitors()` and the display sink branch entirely,
- silences `playsound` (and skips the `gtts` startup file generation that requires network anyway),
- leaves the existing default behaviour (display + audio) unchanged for users on Pi OS with Desktop.

**In scope:** code changes in `community_projects/watcher/`, config-example updates, README note, a systemd unit template to replace the desktop-autostart launcher.

**Not in scope:** changing any input source (`rpi`/`libcamera`/USB/file all already work headless), reimaging the production Pi, the `basic_pipelines/` upstream examples.

## Pre-flight

1. Branch from `main`: `git checkout -b headless-watcher-mode`.
2. Confirm the four call sites are still as documented before editing — the line numbers below were captured against the current commit and may have drifted:
   ```bash
   grep -n "get_monitors\|xvimagesink\|playsound\|create_speech_files" \
       community_projects/watcher/gstreamer_watcher_app.py \
       community_projects/watcher/watcher_base.py
   ```
3. Confirm `NEW_DISPLAY_PIPELINE` in the three per-app `gstreamer_*_app.py` files is still dead code (defined but never called):
   ```bash
   grep -n "NEW_DISPLAY_PIPELINE" community_projects/watcher/*/gstreamer_*_app.py
   ```
   If any subclass has started using it, that call site must be patched the same way as the base.

## Step 1 — Add the `HEADLESS` config flag

Add a single key to each app's `config-example.json`:

```json
"HEADLESS": false
```

Files:
- [community_projects/watcher/bluebox/config-example.json](community_projects/watcher/bluebox/config-example.json)
- [community_projects/watcher/helen-o-matic/config-example.json](community_projects/watcher/helen-o-matic/config-example.json)
- [community_projects/watcher/peetronic/config-example.json](community_projects/watcher/peetronic/config-example.json)
- [community_projects/watcher/pigeonator/config-example.json](community_projects/watcher/pigeonator/config-example.json)

Default `false` so existing deployments are unchanged. Per-deployment `config.json` overrides it on the headless box.

Allow an env-var override too (matches the existing `WATCHER_OUTPUT_DIRECTORY` / `WATCHER_CONFIG_FILE` pattern):
```python
headless = os.environ.get("WATCHER_HEADLESS", "").lower() in ("1", "true", "yes") \
           or config.get("HEADLESS", False)
```
This lets `start_watcher.sh` flip headless mode without editing config files (handy for tests).

## Step 2 — Plumb the flag through `WatcherBase`

In [community_projects/watcher/watcher_base.py](community_projects/watcher/watcher_base.py):

1. In `__init__` (around line 54, next to the other `config.get(...)` reads), add:
   ```python
   self.headless = os.environ.get("WATCHER_HEADLESS", "").lower() in ("1", "true", "yes") \
                   or config.get("HEADLESS", False)
   if self.headless:
       self.logger.info("HEADLESS mode enabled — skipping display sink and audio playback")
   ```
2. Guard the TTS file generation at line 62:
   ```python
   if not self.headless:
       self.create_speech_files()
   ```
   (Reason: `gtts` is a network call to translate.google.com and writes a file that is only ever consumed by `playsound`. No point doing either on a headless box, and it removes a cold-start network dependency.)
3. Guard the alert playback at line 292:
   ```python
   if not self.headless:
       self.playsound_async(CLASS_ALERT)
   ```
   Leave `playsound_async` itself alone — no need to make it a no-op globally.

## Step 3 — Make the display sink conditional in the GStreamer base

In [community_projects/watcher/gstreamer_watcher_app.py](community_projects/watcher/gstreamer_watcher_app.py):

1. Wrap `get_screen_resolution` (line 93) so it doesn't crash without a display:
   ```python
   def get_screen_resolution():
       """Get current screen resolution; returns a sensible default if no display is attached."""
       try:
           monitor = get_monitors()[0]
           return monitor.width, monitor.height
       except Exception:
           return 1280, 720
   ```
   This is a defence-in-depth fix even outside headless mode — `screeninfo` raises `IndexError` when called inside an SSH session without `DISPLAY` set, which has bitten anyone trying to run a Watcher remotely.
2. Read the headless flag on the `GStreamerWatcherApp` instance (it has `self.user_data`, which is the `WatcherBase` subclass — `self.user_data.headless` is available). In `get_pipeline_string` (around line 236), replace the unconditional display branch with:
   ```python
   if getattr(self.user_data, "headless", False):
       display_pipeline = f'{QUEUE(name="hailo_display_q")} ! fakesink sync=false'
   else:
       display_pipeline = DISPLAY_PIPELINE(
           video_sink="xvimagesink",
           sync=self.sync,
           show_fps=self.show_fps,
       )
   ```
   `fakesink sync=false` is the right choice over `autovideosink`: it never blocks the pipeline on missing clock sync, never tries to negotiate a display, and the user-callback branch (which is what writes the video file and feeds the web UI) is upstream of the sink so detection still happens.

## Step 4 — Cull the dead `NEW_DISPLAY_PIPELINE` copies

The three per-app `gstreamer_*_app.py` files each carry an unused `NEW_DISPLAY_PIPELINE` function with the same `xvimagesink` default. Either:

- (a) **delete them**, since they are dead code, or
- (b) leave them and add a comment that they aren't used.

Recommended: **(a)**. If anyone ever wires one back in they'll get the headless-broken behaviour back too. Files:
- [community_projects/watcher/bluebox/gstreamer_bluebox_app.py:103-132](community_projects/watcher/bluebox/gstreamer_bluebox_app.py#L103-L132)
- [community_projects/watcher/peetronic/gstreamer_peetronic_app.py:103-132](community_projects/watcher/peetronic/gstreamer_peetronic_app.py#L103-L132)
- [community_projects/watcher/pigeonator/gstreamer_pigeonator_app.py:103-132](community_projects/watcher/pigeonator/gstreamer_pigeonator_app.py#L103-L132)

Also drop the `from gstreamer_watcher_app import ... DISPLAY_PIPELINE` import on line 5 of each file if `DISPLAY_PIPELINE` is no longer referenced after the cull.

## Step 5 — Make `screeninfo`, `gtts`, `playsound` optional in requirements

These three packages currently sit in each app's [requirements.txt](community_projects/watcher/pigeonator/requirements.txt). On Lite they install fine, so this isn't strictly required, but they pull in transitive deps (`PyObjC`-style audio backends on some systems) that are pure overhead in headless mode.

Two options:

- **Cheap option**: leave them in `requirements.txt` and rely on the runtime guards from Steps 2/3. The packages get installed but never imported at the wrong moment because the imports happen at module load — so this only works if the imports themselves succeed on Lite. They do (verified: `screeninfo` imports cleanly without a display, it only fails when `get_monitors()` is called; `gtts` and `playsound` import without an audio device).
- **Clean option**: move the three imports inside their respective methods so the modules aren't imported at all in headless mode, and split the requirements into `requirements.txt` (always) and `requirements-display.txt` (desktop-only).

Recommended: **cheap option** for this PR — keep the change small. Revisit if the package set actually causes a problem on Lite.

## Step 6 — systemd unit to replace the desktop-autostart path

[start_watcher_on_login.sh](community_projects/watcher/pigeonator/start_watcher_on_login.sh) is presumably wired into the LXDE autostart on the existing Pi. On Lite there is no graphical login, so each app needs a systemd service.

Add a template at `community_projects/watcher/systemd/watcher@.service` (one templated unit, instantiated per app):

```ini
[Unit]
Description=Watcher app: %i
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=bower
WorkingDirectory=/home/bower/hailo-rpi5-examples/community_projects/watcher/%i
Environment=WATCHER_HEADLESS=1
ExecStart=/bin/bash -lc 'cd /home/bower/hailo-rpi5-examples && source setup_env.sh && cd community_projects/watcher/%i && exec ./start_watcher.sh'
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable per-app:
```bash
sudo systemctl enable --now watcher@pigeonator.service
sudo systemctl enable --now watcher@bluebox.service
# etc.
```

`WatcherBase` will pick up `WATCHER_HEADLESS=1` from the unit's `Environment=` line, so the same code base runs identically on desktop (config flag false) and Lite (env var set).

Note: `start_watcher.sh` currently runs the python command with a trailing `&` which detaches it from the shell. systemd needs the process in the foreground, so either:
- (a) edit `start_watcher.sh` to drop the `&` and use `exec python ...` when `WATCHER_HEADLESS` is set, or
- (b) bypass `start_watcher.sh` in the unit and put the `python pigeonator.py ...` command directly in `ExecStart`.

Option (b) is simpler and keeps the existing desktop launcher untouched.

## Step 7 — Update the README and CLAUDE.md

In the per-app READMEs (or a new `community_projects/watcher/HEADLESS.md`), document:
- The `HEADLESS` config flag and the `WATCHER_HEADLESS` env var.
- The systemd unit template and how to instantiate it.
- That `screeninfo` / `gtts` / `playsound` are still installed but unused.
- That the web UI on `https://<pi>:<port>` is the only operator interface in this mode.

Add a short note to [CLAUDE.md](CLAUDE.md) under the Watcher framework section so future Claude sessions know the flag exists. One line is enough.

## Smoke tests

On a desktop Pi (regression — defaults must be unchanged):

1. With `HEADLESS` absent from `config.json` and `WATCHER_HEADLESS` unset, run pigeonator. Expect: window appears, audio plays on first detection. **Before/after must be identical.**
2. With `HEADLESS: true` in config, run pigeonator on the same desktop Pi. Expect: no window, no audio, but web UI still works and detection events still get written to `output/YYYYMMDD/`.

On a fresh Pi OS Lite install (the actual target):

3. `source setup_env.sh && pip freeze | grep -E 'screeninfo|gtts|playsound'` — confirm the deps install cleanly with no X11 transitive crashes.
4. `WATCHER_HEADLESS=1 python pigeonator.py --use-frame --hef-path ... --input rpi`. Expect: pipeline starts, no `IndexError` from `get_monitors`, no `playsound` errors, `https://<pi>:5001` reachable from another machine.
5. Trigger a detection (walk a pigeon plushie past the camera, or feed a test video via `python -m testing.test_runner --filter app_type=pigeonator`). Confirm the JSON/MP4/JPG triple lands in `output/`.
6. Reboot. Confirm `systemctl status watcher@pigeonator` shows `active (running)` after boot, no manual login required.

## Rollback

The change is config-flag-gated; rollback is `HEADLESS: false` (or unset `WATCHER_HEADLESS`) plus disabling the systemd unit:

```bash
sudo systemctl disable --now watcher@pigeonator.service
```

If the code changes themselves introduce a regression on the desktop Pi, `git revert` the merge commit — there are no schema or output-format changes, so old `output/` data and `metadata.json` files remain valid.

## Open questions

1. Do we need to keep the `NEW_DISPLAY_PIPELINE` dead-code copies for any reason that isn't visible from the source (e.g. somebody's WIP branch)? If yes, Step 4 stays as option (b).
2. Is there a future need for an in-memory video preview over the web UI (e.g. MJPEG stream of the live pipeline)? If yes, the right place to add it is the `fakesink` branch in Step 3 — replace `fakesink` with a `tee` + `multipartmux` + `tcpserversink` (or an `appsink` feeding Flask). Out of scope for this plan but the architecture is set up to allow it.
