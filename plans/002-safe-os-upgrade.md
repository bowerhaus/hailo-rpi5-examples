# Plan: Safe Raspberry Pi OS update on Watcher production Pi

## Context

The Pi 5 in question runs four long-lived Watcher services (bluebox, helen-o-matic, peetronic, pigeonator) against a Hailo-8L M.2 module. The Hailo runtime stack (`hailort`, `hailo-tappas-core`, `libcamera`) is tightly coupled to:
- the M.2 firmware reported by `hailortcli fw-control identify`,
- the GStreamer plugin set used by `hailo_apps_infra` (pulled from GitHub `main` HEAD — no commit pin in [requirements.txt](requirements.txt)),
- the Pi camera path (`libcamerasrc`) used by every Watcher's `--input rpi`.

A blind `apt full-upgrade` is the most common cause of pipelines failing to start: kernel/devicetree changes break the PCIe link, libcamera ABI breaks `libcamerasrc`, and a new TAPPAS/HailoRT pulled in by APT desyncs from the firmware. The goal of this plan is a routine OS catch-up that leaves the Hailo stack untouched, with a documented rollback and explicit smoke tests against each Watcher app before the holds are released.

**Not in scope:** major distro version jumps (Bookworm → Trixie etc.). Those need a separate plan with a clean reimage path.

## Pre-flight (do not skip)

1. **Clone the boot media.** Power down, pull the SD/NVMe, image with `rpi-clone` (or `dd if=/dev/... of=backup.img bs=4M status=progress`) to an external disk. This is the rollback. Restore by reflashing.
2. **Record current versions** so a regression has a fixed reference point:
   ```bash
   uname -r
   hailortcli fw-control identify
   dpkg -l | grep -E 'hailo|libcamera|gstreamer1.0' > ~/pre-upgrade-versions.txt
   pip --version && (source setup_env.sh && pip freeze) > ~/pre-upgrade-pip.txt
   ```
3. **Stop the Watcher services** so the upgrade isn't fighting live processes:
   ```bash
   pkill -f bluebox.py
   pkill -f helen_o_matic.py
   pkill -f peetronic.py
   pkill -f pigeonator.py
   ```
   (If any are run via `start_watcher_on_login.sh` / a `cron @reboot` / systemd unit, disable that path for the duration of the upgrade.)

## Step 1 — Hold the coupled packages

```bash
sudo apt-mark hold \
    hailort hailort-pcie-driver \
    hailo-tappas-core hailo-all \
    libcamera0 libcamera-apps libcamera-apps-lite \
    raspberrypi-kernel raspberrypi-kernel-headers
```

Notes:
- The repo currently has **no existing holds** (Explore confirmed: no `apt-mark` references anywhere in the tree).
- Including the kernel package set guards against devicetree / PCIe changes that have historically broken the Hailo-8L link.
- If a name above is not installed on this image, `apt-mark hold` is a no-op — safe to leave in.

Verify:
```bash
apt-mark showhold
```

## Step 2 — Routine APT upgrade

```bash
sudo apt update
sudo apt upgrade        # NOT full-upgrade / dist-upgrade
sudo apt autoremove --purge
```

Prefer `upgrade` over `full-upgrade`: the latter is allowed to remove held packages' reverse-deps to satisfy a dependency change, which is exactly the failure mode we are trying to avoid. If `apt upgrade` reports "kept back" packages, **leave them kept back** — do not force them through.

Reboot before any testing so kernel modules / udev / device tree are at their final state:
```bash
sudo reboot
```

## Step 3 — Smoke tests (in order; stop on first failure)

Run from `/home/bower/Projects/hailo-rpi5-examples`. Each step gates the next.

1. **Environment + device reachability**
   ```bash
   source setup_env.sh
   ```
   This script (`setup_env.sh:28-47`, `:110-119`) detects `hailo-tappas-core` via pkg-config, picks `venv_hailo_rpi5_examples`, and calls `hailortcli fw-control identify` to set `DEVICE_ARCHITECTURE`. A non-zero return here means the PCIe link or runtime is broken — **stop, restore from the image in the pre-flight step**, do not continue.

2. **PCIe + dmesg sanity**
   ```bash
   lspci | grep -i hailo            # Hailo device must enumerate
   dmesg | grep -iE 'hailo|pcie' | tail -40
   ```

3. **Basic upstream pipeline** — proves `hailo_apps_infra` + GStreamer plugins + display pipeline still function end-to-end without app-specific code:
   ```bash
   python basic_pipelines/detection.py --input rpi
   ```
   Ctrl-C after a few seconds of detections.

4. **Watcher per-app smoke** — bring up each app one at a time, confirm web UI loads, trigger one detection (walk past the camera / play a known-good MP4), confirm the `output/YYYYMMDD/<timestamp>_<class>.{mp4,jpg,json}` triple is written:
   ```bash
   cd community_projects/watcher/bluebox       && ./start_watcher.sh   # Ctrl-C, verify output/
   cd ../helen-o-matic                         && ./start_watcher.sh   # ditto
   cd ../peetronic                             && ./start_watcher.sh   # ditto
   cd ../pigeonator                            && ./start_watcher.sh   # ditto
   ```
   Tail the per-app log (`~/<appname>.log`) for errors. The launch scripts each source `setup_env.sh` and run `<app>.py --use-frame ...` (Explore confirmed in `start_watcher.sh:6` for each app).

5. **Watcher test suite** (canonical regression check, exercises all four apps against recorded MP4s with metadata schema validation per `community_projects/watcher/testing/test_runner` and `testing/schemas/metadata_schema.json`):
   ```bash
   cd /home/bower/Projects/hailo-rpi5-examples/community_projects/watcher
   python -m testing.test_runner
   ```

6. **Optional — upstream test suite** (slower, broader). Only run if the Watcher suite passes:
   ```bash
   cd /home/bower/Projects/hailo-rpi5-examples
   ./run_tests.sh
   ```

## Step 4 — Re-arm production

If every smoke test passes:
```bash
# Re-enable autostart (whatever was disabled in pre-flight)
# Restart each Watcher via its normal launch path
```

## Step 5 — Hailo stack upgrades (separate, deliberate)

**Do not bundle this with the OS upgrade.** When you are ready to update the Hailo stack:

1. Read the [hailo-ai/hailo-apps-infra](https://github.com/hailo-ai/hailo-apps-infra) commit log and the HailoRT release notes; pick a target version that matches the firmware on the M.2 module.
2. Pin the Python side by replacing the bare git URL in [requirements.txt](requirements.txt) with a commit hash:
   ```
   git+https://github.com/hailo-ai/hailo-apps-infra.git@<sha>
   ```
   (Today it is unpinned — `pip install -r requirements.txt --upgrade` inside the venv would otherwise pull whatever `main` is at that moment.)
3. Unhold and upgrade Hailo APT packages:
   ```bash
   sudo apt-mark unhold hailort hailo-tappas-core hailo-all
   sudo apt update && sudo apt install --only-upgrade hailort hailo-tappas-core hailo-all
   ```
4. Update the venv:
   ```bash
   source setup_env.sh
   pip install -r requirements.txt --upgrade
   ```
5. Re-run **all** smoke tests in Step 3, including `python -m testing.test_runner`.
6. Only run `hailortcli fw-update` if the release notes explicitly require it for the HailoRT version you just installed.

## Rollback

- **Best (always works):** reflash the boot media from the pre-flight image.
- **APT-only regression** (kernel / userspace, Hailo unchanged): `sudo apt install <pkg>=<old-version>` using versions captured in `~/pre-upgrade-versions.txt`, then reboot.
- **Venv regression** (only relevant after Step 5): `pip install -r ~/pre-upgrade-pip.txt --force-reinstall` inside the venv.

## Critical files referenced

- [setup_env.sh](setup_env.sh) — venv selection + `DEVICE_ARCHITECTURE` detection
- [install.sh](install.sh) — installs `rapidjson-dev` + venv + requirements
- [requirements.txt](requirements.txt) — `hailo-apps-infra` pulled from GitHub `main` HEAD (no commit pin); `numpy<2.0.0`
- [run_tests.sh](run_tests.sh) — upstream pytest suite
- [community_projects/watcher/testing/test_runner.py](community_projects/watcher/testing/test_runner.py) — Watcher regression suite
- [community_projects/watcher/bluebox/start_watcher.sh](community_projects/watcher/bluebox/start_watcher.sh)
- [community_projects/watcher/helen-o-matic/start_watcher.sh](community_projects/watcher/helen-o-matic/start_watcher.sh)
- [community_projects/watcher/peetronic/start_watcher.sh](community_projects/watcher/peetronic/start_watcher.sh)
- [community_projects/watcher/pigeonator/start_watcher.sh](community_projects/watcher/pigeonator/start_watcher.sh)

## Verification summary

The upgrade is considered safe to leave in place only if **all** of the following pass after reboot:

- [ ] `source setup_env.sh` returns 0 and prints the same `DEVICE_ARCHITECTURE` as before
- [ ] `lspci | grep -i hailo` shows the device, `dmesg` shows no PCIe errors
- [ ] `python basic_pipelines/detection.py --input rpi` produces detections
- [ ] Each of the four Watcher apps starts, serves its web UI, and writes a complete `output/YYYYMMDD/<ts>_<class>.{mp4,jpg,json}` triple on a real detection
- [ ] `python -m testing.test_runner` (from `community_projects/watcher/`) passes
