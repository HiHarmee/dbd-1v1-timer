# DBD 1v1 Timer

**A lightweight, always-on-top overlay stopwatch for Dead by Daylight 1v1 (custom match) rounds.**

Track your round time and first-hit time without tabbing out of the game. A single key
starts a round and records it when the survivor is down; the overlay also detects the
"downed" state on screen and records the round for you.

> **Anti-cheat**: nothing here reads or writes game memory, injects code, hooks the game,
> or simulates input. It runs entirely outside Dead by Daylight. See the
> [Anti-cheat notice](#anti-cheat-notice).

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
2. Double-click **`run_timer.bat`** (or `啟動單挑計時器.bat`).

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

## Anti-cheat notice

This tool is designed to run **outside** the game. It never touches the Dead by Daylight
process, its memory, or its input pipeline.

### What it deliberately does NOT do

| Technique | Used? |
| --- | --- |
| Process memory read / write (`ReadProcessMemory`, `WriteProcessMemory`) | No |
| DLL injection, remote threads (`CreateRemoteThread`, `LoadLibrary`) | No |
| API hooking (`SetWindowsHookEx`, `SetWinEventHook`) | No |
| Input simulation or macros (`SendInput`, `keybd_event`, `mouse_event`, `PostMessage`) | No |
| Kernel drivers or device I/O (`DeviceIoControl`, named device handles) | No |
| Foreground window sniffing (`GetForegroundWindow`) | No - it cannot even tell DBD is running |

### What it actually uses

| API | Purpose | When |
| --- | --- | --- |
| `GetAsyncKeyState` | Poll the state of your bound keys | Only while the timer runs |
| GDI `BitBlt` + `GetDC(None)` | Capture a 93x74 px region of the **desktop** for down detection | **Only if** Auto-detect is enabled |
| `SetWindowLong` / `SetWindowRgn` | Click-through style and window shape for **its own** overlay | Always |
| `ImmAssociateContextW` | Detach the IME from **its own** window | Always |

`GetAsyncKeyState` is a read-only query, not a keyboard hook - the same API used by
push-to-talk in voice chat apps. `BitBlt` captures the desktop, not the game process,
and only when you enable automatic down detection.

### Why it needs administrator rights

Dead by Daylight runs with high integrity under Easy Anti-Cheat. Windows UIPI blocks
hotkey polling from a lower-integrity process, so the launchers elevate to the same
level. Elevation is used for input visibility only - the program asks for no privileges
over the game.

### Is it cheating?

The tool records elapsed time, which a human could measure with a stopwatch. It cannot
read, display, or infer hidden game state (no survivor perks, no positions, no
cooldowns). It never acts on your behalf.

### Risks you accept

- **Easy Anti-Cheat decides.** No third-party tool can guarantee acceptance, and
  detection heuristics can change with any update.
- **Tournaments and official events** usually forbid any external assistance. Do not use
  this there.
- **Publisher terms** prohibit software that grants an unfair advantage. A plain round
  timer is a grey area and enforcement is at Behaviour Interactive's discretion.
- Read-only screen capture (only with Auto-detect on) is the single technical contact
  point with the rendered game image.

### Lowest-footprint mode

Disable **Auto-detect** in Settings. The detection worker is then never started, so the
program performs **zero screen captures** and only polls key states while drawing its own
overlay - equivalent to using a stopwatch.

Use at your own risk. This is an unofficial companion tool, not affiliated with or
endorsed by Behaviour Interactive Inc.

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
