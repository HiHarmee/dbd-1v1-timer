# DBD 1v1 Timer

**A lightweight, always-on-top overlay stopwatch for Dead by Daylight 1v1 (custom match) rounds.**

Track your round time and first-hit time without tabbing out of the game. A single key
starts a round and records it when the survivor is down; the overlay also detects the
"downed" state on screen and records the round for you.

---

## Highlights

- **One-key round flow** - `T` starts a round, records the down time, and starts the next round.
- **Automatic down detection** - template matching on the red character icon (Dice coefficient),
  so a down is recorded even if you forget to press the key.
- **First-hit mark** - `F2` records only the first hit of the round.
- **Fast screen capture** - GDI capture takes ~11 ms per frame (vs ~54 ms with `ImageGrab`),
  with an automatic fallback when GDI is unavailable.
- **Persistent history** - every round is stored in `history.json` and can be reviewed
  in the Settings window.
- **Cue flashes** - the digits flash at 30 s and 60 s as a quiet timing reminder.
- **Click-through overlay** - lock the HUD with `F4`; it stays on top and never steals focus.
- **Bilingual UI** - English and Traditional Chinese (`zh-TW`), switchable in Settings.
- **Ready-to-ship build** - `build.bat` produces a single `DBDTimer.exe` (no Python needed).

---

## Hotkeys

| Action | Default key | Notes |
| --- | --- | --- |
| Start / record down / next round | `T` | Not started: start a round. Timing: record down and end the round. Already down: start the next round. |
| First hit only | `F2` | Ignored after the first hit of the round. |
| Reset | `Del` | Clears the current round. |
| Toggle click-through lock | `F4` | Also available from the lock button on the HUD. |
| Toggle sound | `F8` | |
| Open settings | Gear button on the HUD | |

All keys and the auto-detection sensitivity are configurable in **Settings > Hotkeys / Auto-detect**.

---

## Requirements

- Windows 10 / 11
- Python 3.10+ (only when running from source)
- `numpy`, `Pillow` (installed automatically by the launcher scripts)

---

## Quick start (from source)

1. Install Python 3.10+ and make sure `python` is on `PATH`.
2. Double-click **`run_timer.bat`** (or the Chinese alias launcher).

What the launcher does:

- requests administrator rights (required - Dead by Daylight runs with high integrity
  through Easy Anti-Cheat, and Windows UIPI blocks hotkey hooks from a lower-integrity process);
- checks for `numpy` and `Pillow` and installs them if missing;
- starts the timer with `pythonw.exe` (no console window);
- writes any startup errors to `timer.log`.

For development, double-click **`run_debug.bat`**: it enables the debug panel and the
ROI box so you can see live match scores.

> If Windows shows a User Account Control prompt, click **Yes**.

---

## Build a single .exe

Double-click **`build.bat`** (installs PyInstaller if needed). Equivalent command:

```bat
python -m PyInstaller --onefile --windowed --uac-admin --name DBDTimer ^
    --add-data "downed_ref_roi.png;." dbd_timer.py
```

Output: `dist\DBDTimer.exe` (a single ~30 MB file, no Python required).

Notes:

- `--onefile` takes 2-4 s to start because it unpacks to a temporary folder.
- The embedded manifest requests administrator rights, so the exe elevates on launch.
- `config.json` and `history.json` are created **next to the exe**; the template is read
  from the bundled resource and falls back to the exe folder.
- Debug mode: create a shortcut whose target is `DBDTimer.exe --debug`.
- Windows may warn about an unsigned binary; choose **More info > Run anyway**.

---

## Settings

The Settings window has six tabs:

| Tab | Purpose |
| --- | --- |
| Hotkeys | Rebind every action |
| Sound | Enable/disable cues and pick volume |
| Auto-detect | Toggle down detection, adjust ROI and match threshold |
| Appearance | Font size, colors, language (English / zh-TW) |
| Startup | Remember HUD position, launch options |
| History | Review recorded rounds (stored in `history.json`) |

An **Advanced / Debug** section is collapsed by default.

---

## How down detection works

1. A small ROI around the survivor status area is captured with GDI (`fast_grab.py`),
   falling back to `PIL.ImageGrab` when needed.
2. The ROI is compared against the stored template `downed_ref_roi.png` using a
   **red-shape Dice coefficient**: only red-dominant pixels are turned into a mask, so
   red clothing or lighting cannot trigger a false positive.
3. A score above `match_threshold` (default `0.5`, configurable) means the survivor is
   down; the round is recorded and the next round is armed automatically.

Typical offline validation of the shipped template: downed = 1.000, injured = 0.263,
healthy = 0.078. Re-calibrate the ROI and threshold in **Settings > Auto-detect** if your
resolution or HUD scale differs.

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Keys do nothing inside the game | Run as administrator (both launcher scripts elevate automatically). |
| Down is not detected | Check the ROI in `--debug`, then lower `match_threshold`. |
| False "down" detections | Raise `match_threshold` to 0.55-0.6. |
| Exe closes immediately | Run `DBDTimer.exe --debug` from a console, or check `timer.log`. |
| HUD is stuck / cannot click | Press `F4` to unlock click-through. |

---

## Project layout

```
dbd_timer.py         HUD, key hooks, round state machine, entry point
auto_detector.py     Background detection loop, ROI capture scheduling
icon_detector.py     Red-shape Dice template matcher
fast_grab.py         GDI screen capture with ImageGrab fallback
config_manager.py    JSON config with defaults, migration and deep merge
history_manager.py   Round history persistence
settings_window.py   Six-tab settings UI
bbox_picker.py       Full-screen ROI picker
i18n.py              English / Traditional Chinese strings
sound_engine.py      Optional cue playback
downed_ref_roi.png   Detection template (required at runtime)
run_timer.bat        One-click launcher (elevates, installs deps)
run_debug.bat        Launcher with debug panel + ROI box
build.bat            One-click PyInstaller build
```

---

## License

Released under the MIT License. See [LICENSE](LICENSE).

Dead by Daylight is a trademark of Behaviour Interactive Inc. This project is an
unofficial companion tool and is not affiliated with or endorsed by Behaviour Interactive.
