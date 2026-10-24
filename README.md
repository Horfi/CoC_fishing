# Clash of Critters Fishing Bot

Automates the fishing event in Clash of Critters on BlueStacks: cast, pull, complete skill checks, collect rewards, and repeat.

**The included images support the Polish game interface. If you use Polish, you do not need to replace any images.**

## 1. Install and open the game

1. Install Python 3.11 or newer. Enable **Add Python to PATH** in the installer.
2. Install BlueStacks and open Clash of Critters.
3. Set the game language to **Polish** and open the fishing event at the green cast button.
4. Download and extract this repository, or clone it.
5. Open PowerShell in the project folder containing `setup.ps1` and `run.ps1`.

## 2. Set up the bot

Run once to install the dependencies:

```powershell
.\setup.ps1
```

## 3. Select the game area and try one cast

```powershell
.\run.ps1 -Calibrate -MaxCasts 1
```

Drag a rectangle around **only the game area**:

- Start below the BlueStacks title bar.
- End above the bottom black strip containing the X.
- Leave out advertisements and the right-hand emulator toolbar.
- Press **Enter** to confirm.

Move the preview window beside the game so it does not cover it. The bot starts in watch-only mode and will not click yet.

Press **F8** to start. Let it complete one fishing cycle and collect the reward. Press **F9** or **Escape** to exit.

Keep BlueStacks visible and do not use the mouse in other apps while the bot is running. Run calibration again whenever you move or resize the game window.

## 4. Run more casts

```powershell
.\run.ps1 -MaxCasts 10
```

Press **F8** to start. Change `10` to the number of casts you want. The limit resets each time you restart the script.

## Controls

| Key | Action |
| --- | --- |
| F8 | Start or pause clicking |
| F9 / Escape | Exit |
| F7 | Save screenshots and detection details to `captures/` |

The preview shows the detected state, click position, skill target, moving marker, and number of skill clicks sent.

## Useful commands

Run these from the project folder:

| What you want | Command |
| --- | --- |
| Install or update dependencies | `.\setup.ps1` |
| Re-select the game area and test | `.\run.ps1 -Calibrate -MaxCasts 1` |
| Run 50 casts | `.\run.ps1 -MaxCasts 50` |
| Reduce preview work | `.\run.ps1 -MaxCasts 10 -PreviewFps 5` |
| Run without the preview window | `.\run.ps1 -MaxCasts 10 -NoPreview` |
| Show detailed detection/click logs | `.\run.ps1 -MaxCasts 1 -DebugLog` |
| Adjust assumed click delay | `.\run.ps1 -MaxCasts 1 -LatencyMs 35` |

F8, F9, and F7 still work without a preview. Leave timing settings at their defaults unless clicks consistently miss. Higher FPS settings cannot overcome slow screen capture or emulator performance.

If PowerShell blocks scripts, use these commands instead; they apply the execution-policy override only to that process:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
powershell -ExecutionPolicy Bypass -File .\run.ps1 -Calibrate -MaxCasts 1
```

## Which images should I change?

**For the Polish interface: none. Calibrate first.**

| Folder/file | Purpose | Should you edit it? |
| --- | --- | --- |
| `assets/` | Image templates the bot uses to recognize the game | Only if changing language or the UI appearance changes |
| `captures/` | F7 screenshots and diagnostic files | No. Adding images here does not teach the bot anything |
| `tests/fixtures/` | Example screens used by automated tests | No. These are not runtime detection templates |
| `config.json` | Saved position and size of your game area | Use `-Calibrate` to update it |
| `fishing/vision.py` | Detection regions, colors, and thresholds | Only for detection changes that calibration/templates cannot fix |

### Using another game language

Replace these files **inside `assets/`**, keeping their filenames:

| File | Replace it with |
| --- | --- |
| `bite.png` | A tight crop of the bite/reel-in prompt in your language |
| `collect-text.png` | A tight crop of the Collect button text, equivalent to “Odbierz teraz” |
| `reward-title.png` | A crop of the reward heading, equivalent to “Nagrody!” |
| `collect-white.png` | A black-and-white mask of the Collect button's white text; see below |

Use screenshots with the game area normalized to **500 × 820 pixels**, and match the existing crop sizes as closely as possible. Do not replace these small templates with full-screen screenshots.

To rebuild `collect-white.png`, crop the green Collect button, resize it to **230 × 60 pixels**, and make its white lettering white on a black background. Keep pixels with OpenCV HSV saturation **0–85** and brightness **170–255**. Save the crop `mask[10:48, 15:215]` as `assets/collect-white.png` (200 × 38 pixels).

Leave `ready.png` (rod-button icon) and `marker.png` (moving float) alone unless those icons change. Different text lengths or layouts may also need changes to the search regions in `fishing/vision.py`. Restart the bot and test one cast after replacing templates.

### What about gold, purple, blue, and red reward screens?

These panels are recognized by their **colors and layout in `fishing/vision.py`**. They do not need separate full-screen images in `assets/` or `captures/`.

The bot also recognizes the Collect button on reward dialogs that skip skill checks. After collecting, it waits for the green cast button before starting again.

## If something goes wrong

1. Press **F8** to pause, or **F9** to exit.
2. Make sure BlueStacks is visible and the preview does not cover the game.
3. Recalibrate if you moved or resized the window.
4. Restart with `.\run.ps1 -MaxCasts 1 -DebugLog`.
5. Press **F7** while the problem screen is visible. Check the newest `-raw.png`, `-overlay.png`, and `.json` files in `captures/`.

If you need clarification, **ask ChatGPT or another AI assistant**. Share the relevant code, error message, and diagnostic files, and explain what happened versus what you expected. Review screenshots before sharing them because they may contain private information.

The bot saves diagnostics locally; it does not upload them. Setup needs internet access to install dependencies. `captures/`, `config.json`, and `.venv/` are excluded from Git.

## License

Code and documentation: [MIT License](LICENSE).
Game artwork and screenshots remain the property of their respective rights holders.
